#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::io::{BufRead, BufReader};
use std::process::{Child, ChildStdin};
use std::sync::{mpsc, Mutex, OnceLock};
use std::thread;

use std::{
    io::Write,
    path::PathBuf,
    process::{Command, Stdio},
    time::{Duration, Instant},
};

use tauri::{path::BaseDirectory, Manager};

fn candidate_pythons() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(p) = std::env::var("TRINITY_PYTHON") {
        out.push(PathBuf::from(p));
    }
    if let Ok(home) = std::env::var("HOME") {
        let h = PathBuf::from(home);
        for p in [
            "miniconda3/bin/python3",
            "anaconda3/bin/python3",
            ".pyenv/shims/python3",
            ".venv/bin/python3",
        ] {
            out.push(h.join(p));
        }
    }
    for p in [
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ] {
        out.push(PathBuf::from(p));
    }
    out.push(PathBuf::from("python3"));
    out
}
fn python_with_numpy() -> Result<PathBuf, String> {
    // The Python/NumPy probe itself can take ~150 ms. Resolve it once per app.
    static PYTHON: OnceLock<Result<PathBuf, String>> = OnceLock::new();
    PYTHON.get_or_init(find_python_with_numpy).clone()
}
fn find_python_with_numpy() -> Result<PathBuf, String> {
    for path in candidate_pythons() {
        if let Ok(o) = Command::new(&path)
            .arg("-c")
            .arg("import numpy;print(numpy.__version__)")
            .output()
        {
            if o.status.success() {
                return Ok(path);
            }
        }
    }
    Err("Python 3 com NumPy não encontrado. Configure TRINITY_PYTHON ou instale numpy no Python do Mac.".into())
}
fn backend_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .resolve("solver_backend/runner.py", BaseDirectory::Resource)
        .map_err(|e| format!("Falha ao resolver recurso: {e}"))?;
    if !path.is_file() {
        return Err(format!(
            "Solver empacotado não encontrado: {}",
            path.display()
        ));
    }
    Ok(path)
}
#[tauri::command]
fn solver_status(app: tauri::AppHandle) -> serde_json::Value {
    let py = python_with_numpy();
    let script = backend_path(&app);
    serde_json::json!({"ok":py.is_ok() && script.is_ok(),
        "engine":"TRINITY_SOLVER_ENGINE_V1", "version":"5.0.1",
        "python":py.as_ref().map(|p|p.display().to_string()).unwrap_or_default(),
        "backend_bundled":script.is_ok(), "error":py.err().or_else(||script.err()),
        "capabilities":["linear_system","anomaly_scan","relation_search"],
        "e11_decision_policy_active":false})
}
// A local long-lived Python worker amortizes interpreter and NumPy startup.
// JSON-lines protocol, one request at a time, no network listener.
struct PythonWorker {
    child: Child,
    stdin: ChildStdin,
    replies: mpsc::Receiver<Result<Vec<u8>, String>>,
}

impl PythonWorker {
    fn start(py: &PathBuf, script: &PathBuf) -> Result<Self, String> {
        let mut child = Command::new(py)
            .arg("-u")
            .arg(script)
            .arg("--serve")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("Falha ao iniciar worker Python: {e}"))?;
        let stdin = child.stdin.take().ok_or("stdin do worker indisponível")?;
        let stdout = child.stdout.take().ok_or("stdout do worker indisponível")?;
        let (tx, replies) = mpsc::channel();
        thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                let mut line = Vec::new();
                match reader.read_until(b'\n', &mut line) {
                    Ok(0) => break,
                    Ok(_) => {
                        if tx.send(Ok(line)).is_err() {
                            break;
                        }
                    }
                    Err(err) => {
                        let _ = tx.send(Err(format!("Falha na leitura do worker: {err}")));
                        break;
                    }
                }
            }
        });
        Ok(Self {
            child,
            stdin,
            replies,
        })
    }

    fn request(&mut self, data: &str) -> Result<serde_json::Value, String> {
        if data.len() > 2_000_000 {
            return Err("Entrada excede 2 MB".into());
        }
        self.stdin
            .write_all(data.as_bytes())
            .and_then(|_| self.stdin.write_all(b"\n"))
            .and_then(|_| self.stdin.flush())
            .map_err(|e| format!("Falha ao enviar problema ao Python: {e}"))?;
        let reply = self
            .replies
            .recv_timeout(Duration::from_secs(35))
            .map_err(|e| format!("Worker Python indisponível ou excedeu 35 segundos: {e}"))??;
        if reply.len() > 2_000_001 {
            return Err("Resposta do worker excedeu 2 MB".into());
        }
        serde_json::from_slice(&reply)
            .map_err(|e| format!("Resposta inválida do worker Python: {e}"))
    }
}

impl Drop for PythonWorker {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn run_python(py: PathBuf, script: PathBuf, data: String) -> Result<serde_json::Value, String> {
    static WORKER: OnceLock<Mutex<Option<PythonWorker>>> = OnceLock::new();
    let state = WORKER.get_or_init(|| Mutex::new(None));
    let mut guard = state.lock().map_err(|_| "Worker Python: estado inválido")?;
    if guard.is_none() {
        *guard = Some(PythonWorker::start(&py, &script)?);
    }
    let result = guard.as_mut().expect("worker initialized").request(&data);
    if result.is_err() {
        // Restart the worker on the next call. Kill also covers timeouts.
        *guard = None;
    }
    result
}

#[tauri::command]
async fn solver_run(
    app: tauri::AppHandle,
    problem: serde_json::Value,
    seed: i64,
) -> Result<serde_json::Value, String> {
    if !problem.is_object() {
        return Err("Problema deve ser objeto JSON".into());
    }
    let py = python_with_numpy()?;
    let script = backend_path(&app)?;
    let request = serde_json::json!({"problem":problem,"seed":seed}).to_string();
    tauri::async_runtime::spawn_blocking(move || run_python(py, script, request))
        .await
        .map_err(|e| format!("Falha no executor: {e}"))?
}
/// Run user-provided *trusted* Python code, maintaining the legacy Target API.
/// The script has the invoking user's local filesystem permissions, as the old app did.
/// Output goes to temporary files to avoid pipe deadlocks with verbose targets.
fn run_target_python(py: PathBuf, script: String) -> Result<String, String> {
    if script.len() > 192_000 {
        return Err("Target maior que 192 KB".into());
    }
    if script.trim().is_empty() {
        return Err("O Target está vazio".into());
    }
    let workspace = std::env::var("TRINITY_WORKSPACE")
        .ok()
        .map(PathBuf::from)
        .filter(|p| p.is_dir());
    let cwd = workspace
        .clone()
        .or_else(|| std::env::var("HOME").ok().map(PathBuf::from))
        .unwrap_or_else(std::env::temp_dir);
    let mut paths = vec![cwd.clone(), cwd.join("core")];
    if let Ok(previous) = std::env::var("PYTHONPATH") {
        paths.extend(std::env::split_paths(&previous));
    }
    let python_path = std::env::join_paths(paths).map_err(|e| e.to_string())?;
    let serial = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let base =
        std::env::temp_dir().join(format!("trinity_target_{}_{}", std::process::id(), serial));
    let out_file = base.with_extension("out");
    let err_file = base.with_extension("err");
    // Keep Target output private; do not follow existing temp-file symlinks.
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let stdout = options.open(&out_file).map_err(|e| e.to_string())?;
    let stderr = options.open(&err_file).map_err(|e| e.to_string())?;
    let mut child = Command::new(&py)
        .arg("-u")
        .arg("-c")
        .arg(script)
        .current_dir(&cwd)
        .env("PYTHONPATH", python_path)
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|e| format!("Erro ao executar Target: {e}"))?;
    let start = Instant::now();
    let mut timeout = false;
    let status = loop {
        if let Some(st) = child.try_wait().map_err(|e| e.to_string())? {
            break st;
        }
        if start.elapsed() > Duration::from_secs(180) {
            timeout = true;
            let _ = child.kill();
            break child.wait().map_err(|e| e.to_string())?;
        }
        std::thread::sleep(Duration::from_millis(40));
    };
    fn read_limited(path: &std::path::Path) -> String {
        use std::io::Read;
        let mut buf = vec![];
        if let Ok(file) = std::fs::File::open(path) {
            let _ = file.take(1_000_000).read_to_end(&mut buf);
        }
        String::from_utf8_lossy(&buf).to_string()
    }
    let stdout = read_limited(&out_file);
    let stderr = read_limited(&err_file);
    let _ = std::fs::remove_file(&out_file);
    let _ = std::fs::remove_file(&err_file);
    let content = if stderr.is_empty() {
        stdout
    } else {
        format!("{stdout}\n[STDERR]\n{stderr}")
    };
    if timeout {
        return Err(format!(
            "Target ultrapassou 180 segundos. Saída parcial:\n{}",
            content
        ));
    }
    if !status.success() {
        return Err(format!(
            "Target terminou com código {:?}:\n{}",
            status.code(),
            content
        ));
    }
    Ok(content)
}

#[tauri::command]
async fn run_python_script(script: String) -> Result<String, String> {
    let py = python_with_numpy()?;
    tauri::async_runtime::spawn_blocking(move || run_target_python(py, script))
        .await
        .map_err(|e| format!("Falha na execução Target: {e}"))?
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            solver_status,
            solver_run,
            run_python_script
        ])
        .run(tauri::generate_context!())
        .expect("failed to start Trinity Solver 11x11");
}

#[cfg(test)]
mod target_tests {
    use super::*;
    #[test]
    fn persistent_worker_reuses_child() {
        let py = python_with_numpy().expect("Python+NumPy required");
        let script = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("solver_backend/runner.py");
        let mut worker = PythonWorker::start(&py, &script).unwrap();
        let first_pid = worker.child.id();
        let first = worker
            .request(r#"{"problem":{"kind":"linear_system","A":[[2]],"b":[6]}}"#)
            .expect("first solver request failed");
        assert_eq!(first["ok"], true);
        assert_eq!(first["result"]["output"]["solution"][0], 3.0);
        let second = worker
            .request(r#"{"problem":{"kind":"linear_system","A":[[3]],"b":[12]}}"#)
            .expect("second solver request failed");
        assert_eq!(second["ok"], true);
        assert_eq!(second["result"]["output"]["solution"][0], 4.0);
        assert_eq!(worker.child.id(), first_pid);
        assert!(worker.child.try_wait().unwrap().is_none());
    }
    #[test]
    fn solver_bridge_drains_large_json_without_deadlock() {
        use std::fs;
        let py = python_with_numpy().expect("Python+NumPy required");
        let temp =
            std::env::temp_dir().join(format!("trinity_bridge_large_{}.py", std::process::id()));
        fs::write(
            &temp,
            "import json\nprint(json.dumps({'ok': True, 'payload': 'A' * 200000}))\n",
        )
        .unwrap();
        let output = run_python(py, temp.clone(), "{}".into());
        let _ = fs::remove_file(temp);
        let output = output.expect("large JSON must not deadlock");
        assert_eq!(output["ok"], true);
        assert_eq!(output["payload"].as_str().unwrap().len(), 200000);
    }
    #[test]
    fn executes_trusted_python_target_and_captures_output() {
        let py = python_with_numpy().expect("Python+NumPy required");
        let result=run_target_python(py,"print('TRINITY_TARGET_OK')\nfrom core.primary_core import solve_problem\nr=solve_problem({'kind':'linear_system','A':[[2]],'b':[6]})\nprint(r['output']['solution'])\n".into()).unwrap();
        assert!(result.contains("TRINITY_TARGET_OK"));
        assert!(result.contains("[3.0]"));
    }
    #[test]
    fn captures_python_errors_without_silent_success() {
        let py = python_with_numpy().expect("Python+NumPy required");
        let error = run_target_python(py, "raise RuntimeError('TARGET_EXPECTED_ERROR')".into())
            .unwrap_err();
        assert!(error.contains("TARGET_EXPECTED_ERROR"));
    }
    #[test]
    fn rejects_empty_and_oversized_targets() {
        let py = python_with_numpy().expect("Python+NumPy required");
        assert!(run_target_python(py.clone(), "   ".into()).is_err());
        assert!(run_target_python(py, "x".repeat(192_001)).is_err());
    }
}

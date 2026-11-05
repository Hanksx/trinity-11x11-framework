# Trinity 11x11

Repositório exclusivo do software do Trinity, sem pesquisas científicas.
Inclui núcleo matricial 11x11, motor numérico, interface Trinity Solver 5.0.1
(Tauri, Rust, TypeScript, Python) e testes básicos.

Não inclui Kaggle, arquivos de pesquisas, relatórios, resultados, submissões ou projetos particulares.

Testes:
    python3 -m pip install -r requirements.txt
    python3 -m unittest discover -s tests -v

Interface:
    cd trinity_solver_tauri
    npm ci
    npm run build
    npm run tauri:dev

Segurança: Target Scripts executam código local com permissões do usuário.
Não execute código desconhecido. A licença ainda precisa ser definida.

Para Target Scripts que importam o núcleo, defina TRINITY_WORKSPACE com o caminho da cópia local antes de iniciar o aplicativo.

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

## Verificação e compilação

O GitHub Actions executa testes Python 3.11, 3.12 e 3.13, a compilação do
frontend TypeScript/Vite (Node 22) e a compilação nativa Rust/Tauri no
macOS Intel. O job nativo também gera um pacote de aplicativo `.app`.

Isso verifica a compilação, mas não substitui testes completos da interface.
O pacote atual **não inclui Python ou NumPy**: é necessário instalar ambos
no Mac. Caso o programa não encontre o interpretador, defina a variável
`TRINITY_PYTHON` com o caminho do Python que contém NumPy.

**Segurança:** Target Scripts executam código arbitrário com permissões do
usuário. Não são isolados em sandbox. Scripts JavaScript usam avaliação
 dinâmica na interface; execute somente código próprio ou auditado.

**Desempenho:** a solução de sistemas lineares usa NumPy internamente;
resultado numericamente correto não implica superioridade sobre NumPy/SciPy.
Experimentos e benchmarks privados não fazem parte deste repositório.

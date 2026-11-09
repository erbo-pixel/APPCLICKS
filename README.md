# GG Arena no Streamlit

Aplicativo em português para organizar campeonatos de jogos, equipes, partidas, resultados e classificação. Os dados ficam em `.gg_arena_data.json` na pasta do projeto; backups podem ser importados ou exportados pela tela **Campeonatos**.

## Executar no Windows

No PowerShell, na pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

O Streamlit abrirá o aplicativo no navegador. Se o comando `py` não estiver disponível, instale Python 3.10 ou superior e use o executável do Python para criar o ambiente virtual.

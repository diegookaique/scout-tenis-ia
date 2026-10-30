# Como publicar o app no Streamlit Community Cloud

O Streamlit Community Cloud hospeda apps Streamlit de graça, direto de um repositório público do GitHub. O resultado é um link público, do tipo `https://scout-tenis-ia.streamlit.app`.

## O que já está pronto no código

| Item | Onde |
|---|---|
| Versões fixas das bibliotecas, que o servidor instala sozinho | `requirements.txt` |
| Visual e configuração (tema claro/escuro, sem botão "Deploy" para visitantes) | `.streamlit/config.toml` |
| Banco montado na primeira visita: baixa os CSVs públicos e calcula o Elo, em cerca de 1 a 2 minutos, uma vez por servidor | `src/preparo.py`, chamado em `app.py` |
| Chave lida de `st.secrets` no servidor, ou do `.env` no computador | `app.py` (`_segredo`) |
| Sem chave, o app abre em modo demonstração. Se a cota gratuita acabar, as perguntas de exemplo continuam respondendo | `src/demo.py` e `app.py` |

## Passo a passo

1. Acesse **https://share.streamlit.io** e clique em **Continue with GitHub**. Entre com a conta que tem o repositório `scout-tenis-ia`.
2. Autorize o Streamlit a ler seus repositórios. Ele pede permissão uma vez.
3. Clique em **Create app** e depois em **Deploy a public app from GitHub**.
4. Preencha:
   - **Repository:** `diegookaique/scout-tenis-ia`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** escolha o endereço, por exemplo `scout-tenis-ia`
5. Abra **Advanced settings**:
   - **Python version:** 3.13
   - **Secrets:** cole a linha abaixo, trocando o texto pela sua chave do Gemini (a mesma do `.env`):
     ```toml
     GEMINI_API_KEY = "cole-aqui-a-sua-chave"
     ```
6. Clique em **Deploy**.

Na primeira vez, o servidor instala as bibliotecas (alguns minutos). A primeira pessoa que abrir o app vê a mensagem "Preparando o banco de dados pela primeira vez" por cerca de 1 a 2 minutos. Depois disso, o app abre direto.

## Depois de publicado

- **Atualizar o app:** cada `git push` na `main` atualiza o app sozinho.
- **Trocar a chave:** no painel do app (share.streamlit.io), abra **⋮ → Settings → Secrets**.
- **App "dormindo":** se ninguém abrir o app por alguns dias, ele hiberna. Quem visitar depois clica em "Yes, get this app back up!" e espera um pouco. Como o servidor recomeça do zero, o banco é montado de novo nessa hora.
- **Cota gratuita do Gemini:** todos os visitantes usam a sua chave. Se o limite por minuto acabar, as 10 perguntas de exemplo respondem com as consultas prontas e as perguntas livres pedem para tentar de novo em instantes. Nada é cobrado.
- **Logs:** no canto inferior direito do app publicado, **Manage app** mostra o que o servidor está fazendo, útil se algo der errado.

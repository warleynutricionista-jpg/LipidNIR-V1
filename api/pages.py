"""Páginas HTML mínimas servidas pelo FastAPI: login e confirmação de saída."""

from __future__ import annotations

from html import escape

_STYLE = """
body{font-family:system-ui,sans-serif;background:#f5f6f8;color:#1c2430;margin:0}
main{max-width:22rem;margin:12vh auto;background:#fff;padding:2rem;border-radius:8px;
border:1px solid #d9dee5}
h1{font-size:1.2rem;margin:0 0 1.2rem}
label{display:block;font-size:.85rem;margin:.8rem 0 .25rem}
input{width:100%;box-sizing:border-box;padding:.5rem;border:1px solid #b6bec9;border-radius:4px}
button{margin-top:1.2rem;width:100%;padding:.6rem;border:0;border-radius:4px;
background:#1f4e79;color:#fff;font-weight:600;cursor:pointer}
.error{color:#a12525;font-size:.85rem;margin:0 0 .5rem}
a{color:#1f4e79}
"""


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


def login_page(csrf_token: str, error: str | None = None) -> str:
    error_html = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    return _page(
        "Lipidence-NIR Modular: entrar",
        "<h1>Lipidence-NIR Modular</h1>"
        f"{error_html}"
        '<form method="post" action="/login">'
        f'<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">'
        '<label for="username">Usuário</label>'
        '<input id="username" name="username" autocomplete="username" required autofocus>'
        '<label for="password">Senha</label>'
        '<input id="password" name="password" type="password" '
        'autocomplete="current-password" required>'
        '<button type="submit">Entrar</button></form>',
    )


def logout_page(csrf_token: str, username: str, back_href: str) -> str:
    return _page(
        "Lipidence-NIR Modular: sair",
        f"<h1>Sair da sessão de {escape(username)}?</h1>"
        '<form method="post" action="/logout">'
        f'<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">'
        '<button type="submit">Sair</button></form>'
        f'<p><a href="{escape(back_href, quote=True)}">Voltar</a></p>',
    )

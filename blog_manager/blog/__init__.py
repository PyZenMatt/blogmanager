"""Package init for inner blog app.

Rimuoviamo il vecchio default_app_config errato (puntava a blog.apps.* che non esiste
in produzione) e lasciamo che Django rilevi automaticamente BlogConfig.
Se necessario si può impostare esplicitamente:
	default_app_config = 'blog_manager.blog.apps.BlogConfig'
ma con Django 3.2+ non serve più.
"""

# (Intenzionalmente vuoto per evitare import errati del pacchetto esterno 'blog')

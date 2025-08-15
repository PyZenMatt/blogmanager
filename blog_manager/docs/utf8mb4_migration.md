# Migrazione a utf8mb4 per MySQL

Scopo: abilitare supporto per emoji e caratteri a 4-byte senza cambiare modelli.

Prerequisiti
- Backup completo del database (mysqldump o snapshot su PythonAnywhere)
- Accesso SSH o Console MySQL con privilegi ALTER

Passi (high level)
1. Verifica charset corrente:

```bash
python3 manage.py check_mysql_charset
```

2. Se connection charset non è utf8mb4, aggiusta `settings/prod.py` per forzare `SET NAMES utf8mb4` (giÃ applicato).

3. Migrazione database (esempio):

```sql
ALTER DATABASE `your_db` CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
```

4. Migrazione tabelle (per tutte le tabelle `blog_*`):

```sql
ALTER TABLE `blog_post` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- ripeti per le tabelle interessate
```

5. Test rapido: carica un post con emoji via admin o curl e verifica che non si generi piÃ¹ `Incorrect string value`.

Rollback
- Ripristina il backup se qualcosa va storto.
- Alternativa: riportare le singole tabelle alla collation precedente con `ALTER TABLE ... CONVERT TO CHARACTER SET utf8 COLLATE ...`.

Note PythonAnywhere
- Usa la Console MySQL dal pannello Web o apri una Bash console e usa `mysql -u user -p -h host`.
- Assicurati che il piano DB supporti utf8mb4 (tutte le versioni moderne lo fanno).

Risorse
- https://dev.mysql.com/doc/refman/8.0/en/charset-unicode-sets.html
- https://stackoverflow.com/questions/6571633/what-is-the-difference-between-utf8-and-utf8mb4

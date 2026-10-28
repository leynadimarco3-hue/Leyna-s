# All-State Player Rankings — anonymous ranking poll

This is a working Streamlit application with shared Supabase storage. All voters use the same public URL; only the organizer can see results using the admin password.

## Publish your poll

1. Create a free project at https://supabase.com and open **SQL Editor**. Paste and run the contents of `schema.sql`.
2. Under Supabase **Project Settings → API Keys**, copy your project URL and **service_role** key (or the equivalent secret server key). This key is highly privileged. Never publish it in your repository or send it to voters.
3. Create a private GitHub repository and upload `app.py`, `schema.sql`, `requirements.txt` and this README. Do not upload any real `.streamlit/secrets.toml` file.
4. Go to https://share.streamlit.io, connect GitHub and deploy your repo with `app.py` as the entry point.
5. In Streamlit Cloud **App settings → Secrets**, add the three lines from `.streamlit_secrets_example.toml` with your real values. To generate `ADMIN_PASSWORD_HASH`, run `python -c "import hashlib,getpass;print(hashlib.sha256(getpass.getpass('Admin password: ').encode()).hexdigest())"` on your computer. Save secrets and restart the app.
6. Visit `https://YOUR-APP.streamlit.app/?view=admin` and enter your admin password. Upload an Excel or CSV spreadsheet, then preview and confirm the names.
7. Send voters `https://YOUR-APP.streamlit.app/` (without the admin query parameter). They can rank every player and submit an anonymous ballot.
8. Open your admin link anytime to see points, first-place votes, total ballots, download results, or close voting.

## Spreadsheet format

The first column can contain names, or use a column named `Name`, `Player`, `Player Name`, or `Candidate`. One name per row. Names must be unique. Add a school/team to distinguish identical names.

## Scoring

With N candidates, 1st receives N points, 2nd N-1, and last 1. All ballots must rank every player exactly once. Total points determine results; first-place votes are shown as a secondary sort. The dashboard is private.

## Important limitations

- Voting is anonymous and no voter login is required. **The same person can submit multiple ballots.** If you need one ballot per coach, use invitation tokens or authentication instead.
- This app uses a server-side service-role key in Streamlit secrets. Never expose secrets in source code or browser. Protect the admin password and the private GitHub repository.
- Replacing the candidate list deletes all existing ballots and results. Download results first.
- Anonymous means the app does not ask for or store a voter name; hosting infrastructure may retain standard access logs.
- For larger lists, the dropdown ballot is functional but slower than a drag-and-drop interface.

# Deploying "Sir ND" to Streamlit Community Cloud (Free)

## 1. Get a free Gemini API key
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with a Google account and click **Create API key**.
3. Copy the key somewhere safe — you'll paste it into Streamlit secrets later, never into the code itself.

## 2. Put the project on GitHub
1. Create a new **public or private** repo, e.g. `sir-nd-tutor`.
2. Add these three files to the repo root:
   - `app.py`
   - `requirements.txt`
   - (optional) this `DEPLOYMENT.md`
3. Commit and push:
   ```bash
   git init
   git add app.py requirements.txt
   git commit -m "Initial commit: Sir ND ZIMSEC tutor"
   git branch -M main
   git remote add origin https://github.com/<your-username>/sir-nd-tutor.git
   git push -u origin main
   ```

## 3. Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in with your GitHub account.
2. Click **Create app** → **From existing repo**.
3. Select your `sir-nd-tutor` repo, branch `main`, and main file path `app.py`.
4. Click **Advanced settings** before deploying (or **Settings → Secrets** after deploying) and add:
   ```toml
   GEMINI_API_KEY = "paste-your-real-key-here"
   ADMIN_PASSPHRASE = "choose-a-private-phrase-for-parents"
   ```
   - `GEMINI_API_KEY` is required.
   - `ADMIN_PASSPHRASE` is optional — if you skip it, the app falls back to the
     default phrase `sir nd report` (change this for real use so students can't
     unlock the parent panel).
5. Click **Deploy**. First build takes 1–3 minutes.
6. Your app will be live at a URL like:
   `https://sir-nd-tutor-<random>.streamlit.app`

## 4. Updating the app later
Any time you `git push` a change to `main`, Streamlit Community Cloud
auto-redeploys. To change secrets later, go to your app → **Settings → Secrets**.

## 5. Notes on cost & limits
- Streamlit Community Cloud hosting is free for public GitHub repos.
- Gemini 1.5 Flash has a generous free tier from Google AI Studio, but check
  current rate limits/quotas at https://ai.google.dev/pricing before heavy use.
- The knowledge base (uploaded PDFs/notes) and chat history are stored only in
  the browser session's memory (`st.session_state`) — they reset if the app
  restarts or the student refreshes with a new session. For persistent storage
  across sessions you'd need to add a database (e.g. Supabase, Firebase, or a
  simple SQLite file) — happy to help add that next if you want it.

## 6. Security note on the Admin Panel
The current admin unlock is a shared passphrase (`ADMIN_PASSPHRASE` in
secrets), suitable for a single-family or small-scale deployment. If you plan
to have many different students/parents using one deployed app, consider a
per-family passphrase or a proper login system (e.g. `streamlit-authenticator`)
instead of one shared phrase.

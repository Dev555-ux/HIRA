# Beta Tracking Board

A spreadsheet, not a tool — Notion or Airtable work too, but for 5–10 users a single Google Sheet is genuinely enough, and it's one less thing to set up before the beta starts. `tracking_board.csv` in this folder is a ready-to-import starting point (Google Sheets: File → Import → Upload; Notion: New page → Import → CSV).

## Columns

| Column | Type | Notes |
|---|---|---|
| User | text | Name + business name — you'll have 5–10 rows, no need for an ID |
| Signup date | date | |
| Completed onboarding | checkbox | |
| Uploaded KB | checkbox | |
| Used Demo Chat | checkbox | pair with a count if you want more signal — "used (3 msgs)" beats a bare checkmark |
| Created lead | checkbox | |
| Bugs reported | number | count, with a linked doc/sheet holding the actual reports (see `BUG_REPORT_TEMPLATE.md`) |
| Feature requests | number | same — count here, detail lives elsewhere |
| Last active | date | update this weekly at minimum; it's your best early-warning signal for silent churn |
| Follow-up required | text | not a checkbox — write *what* needs following up ("hasn't touched Demo Chat in 5 days," "asked about pricing, never got an answer") |

## How to use it

- **Update it after every interaction**, not in a weekly batch — a board that's a week stale during a 2-3 week beta is a board you can't actually act on in time.
- **"Last active" is the column to check first, not last.** Someone who signed up, completed onboarding, and then went quiet for 5 days is a bigger problem than someone who reported three minor bugs — they're still engaged. Silence isn't neutral; treat it as a signal.
- **Don't let this replace direct conversations.** The board tells you *what* happened; it doesn't tell you *why* someone stopped. If "Last active" goes stale, that's your cue to reach out personally (see `FOUNDER_PLAYBOOK.md`), not to just note it and move on.
- One row per user, always — don't create a second row for a returning user; update the existing one. The whole point is to see the arc of one person's usage over the beta, not a log of sessions.

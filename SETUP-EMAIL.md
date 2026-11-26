# Email setup: welcome emails and the weekly digest (about 10 minutes, free)

Once this is done:
- everyone who signs up on riverscan.com gets a welcome email straight away
- every Friday the digest goes to every subscriber automatically
- **you get a copy of every email sent** (welcome emails and digests)
- every email has a working unsubscribe link

It runs from your own Google account, so it's free. Gmail can send roughly 100 emails a day this way, which is plenty to start with.

## 1. Make the sheet and paste the script
1. Go to **sheets.new** to create a new Google Sheet. Name it **RiverScan subscribers**.
2. In the sheet, click **Extensions → Apps Script**.
3. Delete the code that's there, then paste in everything from `tools/riverscan-email.gs` in the GitHub repo. Click **Save**.

## 2. Add your two settings
1. In Apps Script, click the **cog (Project Settings)** on the left, then scroll to **Script Properties → Add script property**.
2. Add `OWNER_EMAIL` = `ishanshah2008@icloud.com`
3. Add `TOKEN` = a long random password. Make one up, about 30 random letters and numbers, and keep it for step 4.
4. Click **Save script properties**.

## 3. Turn it on
1. Click **Deploy → New deployment**. Click the cog next to "Select type" and choose **Web app**.
2. Set **Execute as: Me** and **Who has access: Anyone**. Click **Deploy**.
3. Google will ask you to authorise it. Choose your account, then **Advanced → Go to (project) → Allow**. It needs permission to send email and edit the sheet.
4. Copy the **Web app URL**. It looks like `https://script.google.com/macros/s/…/exec`.
5. Optional test: back in the editor, choose `testWelcome` from the function menu and click **Run**. You should get the welcome email.

## 4. Connect it to the site and GitHub
1. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**. Add these three:
   - `SIGNUP_SCRIPT_URL` = the Web app URL
   - `SIGNUP_TOKEN` = the same TOKEN as step 2
   - `OWNER_EMAIL` = `ishanshah2008@icloud.com`
2. Send Claude the Web app URL (or put it in `assets/site-config.js` yourself as `SIGNUP_URL: "…"`). After that, the sign-up form on riverscan.com sends new subscribers there.

## People who signed up before this
Formspree has been emailing you each sign-up. Add those addresses to the sheet by hand: email in column A, today's date in B, `active` in C.

## If you change the script later
Use **Deploy → Manage deployments → Edit → Version: New version → Deploy**, so the same URL keeps working.

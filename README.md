# streak saver

## Streak saver is python CLI app thats automatically sends messages to your friends in tik tok to keep streak alive.

I have lot's of friends who really do care about tik tok streak pets and there was thousands of times when I forgot about this streaks and they was angry on me. So I decided to make script that will do it automaticaly for me every time I turn on my pc. You can customize who and what you're sending, so you can create different messages for all of your friends!

## Technologies

* [Typer](https://typer.tiangolo.com/) - to realize CLI functionality.
* [Playwright](https://playwright.dev/python/) - to interact with tik tok via browser.
* [PyAutostart](https://pypi.org/project/pyautostart/) - to start app every time you turn on your pc.
* [Rich](https://rich.readthedocs.io/en/stable/index.html) - to make prints prettier.

---

## How to use

1. Install package by running `pipx install streak-saver`.
2. Run `streak-saver setup` it'll download playwright deps and create config files. You can also add your friends on this step.
3. Run `streak-saver login` you'll find out browser page with tik tok in there, you need to login to your account once to save cookies. Your data will stay on your pc, no worries.
4. Run `streak-saver autostart --on` to turn run script every time you start your pc(to disable it run `autostart --off`).

**Done!** Now you can either forget about it or use some of the commands lower to customize your messages and to add/remove users who you wanna message.

**Warning**: You should run `streak-saver login` from time to time to renew your cookies. Something like once a week will be enough.

---

## Commands

- `setup` - use only after you download package or if package files corrupted. 
- `login` - use to renew cookies/change account. Necessary before first `send_messages`.
- `add_user USERNAME` - add user to your "users list"(people who you'll be messaging). Use username not nickname!
- `delete_user USERNAME` - delete user from your users list.
- `show_users` - show nicknames and messages that you're senging from the users list.
- `change_default_message MESSAGE` - change default message(by default it's ❤️).
- `change_message_for USERNAME MESSAGE` - change message for specific user from your users list.
- `send_messages` - to send messages for all users from your list(with autostart on runs automatically). Runs only once a day.
- `autostart --on/--off` - use to manage autostart
- `streak-saver` - btw it runs `send_messages` command by default, it's for autostart feature

Successful sends are saved for each recipient. If any recipient fails, the command
reports the underlying error and exits with a nonzero status. Run
`streak-saver send_messages` again to retry failed recipients; friends already
sent a message today will be skipped. The day is marked complete only after all
recipients succeed. Browser confirmation means the message editor cleared the
draft; it does not guarantee delivery to the recipient.

## Deploy with Coolify

The included dashboard lets you scan TikTok conversations, select recipients,
set a default or per-friend message, renew exported browser cookies, and trigger
a send manually. The daily send time is configured in the dashboard in WIB.

1. Push this repository to a Git provider, then in Coolify create an
   **Application** from that repository with the **Docker Compose** build pack.
   Expose port `8000`, attach a domain, and configure `DASHBOARD_USERNAME` and
   `DASHBOARD_PASSWORD` as runtime environment variables.
2. On the Coolify server, create the persistent state directory:

   ```sh
   mkdir -p /data/tiktok-streak/streak_saver
   ```

   The Compose file mounts that directory at `/data`. The app therefore reads
   its files from `/data/streak_saver/` inside the container.
3. Export TikTok cookies as JSON from a browser where TikTok is already logged
   in. Open the dashboard and upload the JSON under **Perbarui cookie**. Common
   browser-extension cookie exports are normalized to Playwright's format
   automatically. Alternatively, perform `streak-saver setup` and
   `streak-saver login` on a computer with a graphical browser and copy the
   resulting state directory. Find it with:

   ```sh
   python -c "import typer; print(typer.get_app_dir('streak_saver'))"
   ```

   Upload its `config.ini` and `cookies.json` to
   `/data/tiktok-streak/streak_saver/` on the Coolify server. Treat
   `cookies.json` as a password; do not commit it to Git.
4. Deploy the application and open its domain to configure recipients and the
   WIB send time. In Coolify open **Scheduled Tasks** and create a task with
   command `streak-saver scheduled_run`, schedule `*/5 * * * *`, and a
   240-second timeout. The task checks the dashboard setting every five minutes,
   catches up if the exact minute was missed, and still sends at most once per
   Jakarta calendar day.

When TikTok cookies expire, sign in again on the graphical computer and replace
the server's `cookies.json`, then run the Coolify task manually to verify it.

For development, install the local package with `python -m pip install -e .`,
install Chromium with `python -m playwright install chromium`, then run
`python -m unittest discover -s tests -v`. Browser tests use locally routed HTML
and never send TikTok messages. They use system `chromium` when available, or the
Playwright browser otherwise; set `STREAK_SAVER_TEST_BROWSER_PATH` to select a
specific browser executable.

 ## Bugs

 If you found bug, please let me know about it by opening issue in github repository🙏

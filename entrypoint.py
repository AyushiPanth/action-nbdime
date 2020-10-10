#!/usr/bin/python3
import asyncio
import html
import os
import queue
import subprocess
import sys
import time
import threading

from nbdime.gitfiles import changed_notebooks
from nbdime.webapp.nbdimeserver import init_app
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from tornado import ioloop

REPO_DIR, BASE_REF, REMOTE_REF, DIFF_DIR = sys.argv[1:5]
REPO_DIR = os.path.abspath(REPO_DIR)
DIFF_DIR = os.path.abspath(DIFF_DIR)
DOWNLOAD_DIR = "/opt/action-nbdime/downloads"
SUMMARY_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Notebook Diff Summary</title>
</head>
<body>
  <ul>
    {list_items}
  </ul>
</body>
</html>
"""
LIST_ITEM_TEMPLATE = '<li><a href="{page}">{text}</a></li>'

dl_path = os.path.join(DOWNLOAD_DIR, "diff.html")
if not os.path.isdir(DIFF_DIR):
    os.makedirs(DIFF_DIR)

xvfb = subprocess.Popen("Xvfb :99 -ac -screen 0 1280x720x16 -nolisten tcp".split(), close_fds=True)

options = webdriver.chrome.options.Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-setuid-sandbox")
options.add_argument("--disable-extensions")
options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
})
driver = webdriver.Chrome(options=options)


def run_server_bg(fbase, fremote, q):
    asyncio.set_event_loop(asyncio.new_event_loop())
    io_loop = ioloop.IOLoop.current(instance=True)
    app, server = init_app(
        on_port=lambda port: q.put(port),
        closable=True,
        difftool_args=dict(base=fbase, remote=fremote),
    )
    io_loop.start()
    # After ioloop ends, clean up after server:
    server.stop()
    q.put(app.exit_code)


links = []
for index, (fbase, fremote) in enumerate(changed_notebooks(BASE_REF, REMOTE_REF, REPO_DIR)):
    q = queue.Queue(maxsize=2)
    server_thread = threading.Thread(target=run_server_bg, name=f"ioloop", args=(fbase, fremote, q))
    server_thread.start()

    port = q.get()
    driver.get(f"http://127.0.0.1:{port}/difftool")
    checkbox = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "nbdime-hide-unchanged"))
    )
    if checkbox.is_selected():
        checkbox.click()
    export_btn = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "nbdime-export"))
    )
    export_btn.click()

    for second in range(10):
        if os.path.isfile(dl_path):
            page_filename = f"diff-{index}.html"
            os.rename(dl_path, os.path.join(DIFF_DIR, page_filename))
            links.append(dict(
                page=page_filename, text=html.escape(f"Diff for {fbase.name} vs {fremote.name}")
            ))
            break
        else:
            time.sleep(1)
    else:
        print("Didn't find file in time, downloaded: " + ", ".join(os.listdir(DOWNLOAD_DIR)))

    close_btn = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.ID, "nbdime-close"))
    )
    close_btn.click()

    server_thread.join(10)

    result = q.get()
    if result != 0:
        raise Exception(f"Server for {fbase.name} vs {fremote.name} exited with result {result}")

if len(links) == 1:
    # One diff - just use it as the front page
    os.rename(
        os.path.join(DIFF_DIR, links[0]["page"]),
        os.path.join(DIFF_DIR, "index.html")
    )
else:
    # Several different files - make a summary front page
    with open(os.path.join(DIFF_DIR, "index.html"), "w") as summary:
        summary.write(SUMMARY_TEMPLATE.format(list_items="\n".join(
            LIST_ITEM_TEMPLATE.format(**link)
            for link in links
        )))
driver.quit()
xvfb.kill()

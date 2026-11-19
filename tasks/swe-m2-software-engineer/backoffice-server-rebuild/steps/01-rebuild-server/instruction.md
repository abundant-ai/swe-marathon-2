# Rebuild the server behind our back office

## Goal

We run our wholesale business on Stockwell, a back-office product. The vendor is gone. What we
have left is the web client and a sealed copy of the server that we can run but not read or
change. I need a server of our own that behaves exactly like the sealed one, so that the client
keeps working and so do the integrations that use the API: the branches' tills, the bank feed and
our accounting export, which compare every value they receive, and its type, exactly.

## Context

- The sealed server is running at `http://127.0.0.1:8080`. It answers a JSON API under `/api`
  and describes its endpoints and their request bodies at `/api/openapi.json`. It runs under its
  own account, so all we can do is use it.
- The web client's source is in `/app/client`: React and TypeScript, with its built copy in
  `/app/client/dist`. It uses most of the API, its screens show what each record means to our
  staff, and nothing in it needs changing.
- The API is large: over two hundred endpoints across selling, stock, buying, production,
  planning and the books.
- Staff attach phone photos, videos, voice notes and supplier PDFs to records, the server reads
  what is inside them, and it prints invoices, packing slips and labels. What they upload is
  whatever their phones, scanners and suppliers produce: scanned multi-page PDFs, encrypted and
  password-protected PDFs, damaged files, large photos and long recordings. `/app/samples`
  holds files of those kinds.
- `POST /api/workspaces` gives you a fresh copy of the demo company, with its own id. Workspaces
  do not affect each other, so make as many as you like to try things out. Every workspace has
  its own calendar, which only moves when you move it.
- Requests inside a workspace name the acting user in the `X-User` header, which our sign-in
  proxy sets; we do not use the server's own passwords, sessions or API keys. The demo company
  comes with one user for each role.
- Money is always a whole number of cents. Dates are written `YYYY-MM-DD`.
- There is no network access. `python3` is Python 3.12 with the packages the vendor's server ran
  on (FastAPI, Starlette, Pydantic, SQLAlchemy, Uvicorn, httpx and their dependencies; see
  `python3 -m pip list`). Node.js and Go are installed with their standard libraries.
- Moving our own company's records across is a separate job; for this one, the demo company is
  all you need.

## What to deliver

A server in `/app/server` with an executable file `/app/server/run` that starts it.

- `run` takes no arguments. It listens on `127.0.0.1` on the port given in the `PORT`
  environment variable and keeps running until it is stopped with SIGTERM, after which it should
  exit promptly. Our service manager gives it 60 seconds after each start to answer
  `GET /api/health`.
- `/app/server` is copied to the machine it will run on: 4 cores and 8 GB of memory, with
  `python3` and its packages, Node.js and Go. A link that points outside the directory is
  replaced there by a copy of what it points to; everything else the server needs must be inside
  `/app/server`. It runs as an unprivileged user that can read that directory and write only to
  the directory named in `DATA_DIR`, with at most 4,096 threads, files of at most 4 GB and 6 GB of
  address space per process.
- One server holds thousands of workspaces in that `DATA_DIR`: each branch's books, and the
  copies we make for training and trials. Everything a workspace holds must survive the server
  being stopped and started again with the same `DATA_DIR`, even when it is killed without
  warning: a change it has answered is kept.
- For every API request the sealed server accepts or refuses, your server gives the same status
  code and the same JSON body, including the calls the web client makes when it opens
  (`GET /api/version`, then `GET /api/ws/{id}/auth/me`). The order of keys inside a JSON object
  does not matter; everything else does, because the integrations compare answers exactly: the
  order of lists, the text of messages, the difference between `1`, `1.0` and `true`, and what a
  workspace holds after a sequence of requests.
- Some answers will differ whatever you do, because they carry the real time or a random token:
  password sign-in, sessions and API keys, which we do not use, and the request log and
  `/metrics`, which are for operators. Those need not match.
- Where the sealed server answers with a file instead of JSON (a document, a label, a
  thumbnail), yours answers with the same bytes and the same `Content-Type`: our document archive
  and our partners' portals file everything we send by its checksum, so a file that differs by
  one byte is a different document to them.
- It takes what the sealed server takes: JSON request bodies of up to 6 MB and file uploads of
  up to 64 MiB.
- Apart from those exceptions, the one thing that may differ is the workspace id itself: our
  proxy routes on it, so yours may be any string of letters, digits and underscores of at most
  40 characters.
- The branches' tills and the back office send up to 8 requests at the same time, and our proxy
  gives up on a request after 30 seconds. Overall it must keep pace with the sealed server: no
  answer should take more than about three times as long as the sealed server takes to give it.
- Our proxy serves the web client's built files itself, so your server only has to answer the
  API.

## Completion

The work is complete when your server cannot be told apart from the sealed one through the API,
apart from the exceptions above. Keep `/app/server/run` working at all times.

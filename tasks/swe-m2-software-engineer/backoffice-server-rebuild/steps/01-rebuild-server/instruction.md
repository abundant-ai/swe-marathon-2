# Rebuild the server behind our back office

## Goal

We run our wholesale business on Stockwell, a back-office product. The vendor is gone. What we
have left is the web client and a sealed copy of the server that we can run but not read or
change. I need a server of our own that behaves exactly like the sealed one, so that the client
and the scripts our staff wrote against the API keep working.

## Context

- The sealed server is running at `http://127.0.0.1:8080`. It serves the web client at `/` and a
  JSON API under `/api`; it also describes its endpoints and their request bodies at
  `/api/openapi.json`. You cannot read its files or its memory; you can only talk to it.
- The web client's source is in `/app/client`: React and TypeScript, with the built copy the
  sealed server serves in `/app/client/dist`. It uses most of the API, its screens show what each
  record means to our staff, and nothing in it needs changing.
- The API is large: over two hundred endpoints across selling, stock, buying, production,
  planning and the books.
- Staff attach photos, videos and PDFs to records, and the server prints invoices, packing
  slips and labels. `/app/samples` holds files of the kinds they upload.
- `POST /api/workspaces` gives you a fresh copy of the demo company, with its own id. Workspaces
  do not affect each other, so make as many as you like to try things out. Every workspace has
  its own calendar, which only moves when you move it.
- Requests inside a workspace name the acting user in the `X-User` header; we sign in through a
  proxy, so passwords, sessions and API keys are not used. The demo company comes with one user
  for each role.
- Money is always a whole number of cents. Dates are written `YYYY-MM-DD`.
- There is no network access. `python3` is Python 3.12 with the packages the vendor's server ran
  on (FastAPI, Starlette, Pydantic, SQLAlchemy, Uvicorn, httpx and their dependencies; see
  `python3 -m pip list`). Node.js and Go are installed with their standard libraries.

## What to deliver

A server in `/app/server` with an executable file `/app/server/run` that starts it.

- `run` takes no arguments. It listens on `127.0.0.1` on the port given in the `PORT`
  environment variable and keeps running until it is stopped. It must start within 60 seconds
  and answer `GET /api/health` once it is ready.
- Everything it needs must be inside `/app/server`, apart from `python3` and its packages, which
  are also on the machine it will run on. It is started by a user that can read
  that directory and write only to the directory named in `DATA_DIR`. It may keep its state in
  memory.
- For every API request the sealed server accepts or refuses, your server gives the same
  status code and the same JSON body. The exceptions are answers that depend on the wall clock
  or on chance, which cannot be reproduced and need not match: the request log, sign-in,
  sessions and API keys, and `/metrics`. The order of keys inside a JSON object does not matter;
  everything else does, including the order of lists, the text of messages, and what a
  workspace holds after a sequence of requests.
- Where the sealed server answers with a file instead of JSON, yours answers with the same
  bytes and the same `Content-Type`.
- Request bodies of up to 6 MB must be accepted.
- The one thing that may differ is the workspace id itself: yours may be any string of letters,
  digits and underscores of at most 40 characters.
- It must cope with many workspaces in use at the same time.
- Serving the web client's files is welcome but not required.

## Completion

The work is complete when your server cannot be told apart from the sealed one through the
API. Keep `/app/server/run` working at all times.

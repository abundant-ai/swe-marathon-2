# Employee desktop integration

Employees launch `Orange.app` on a Mac. Keep the app bundle and an executable `orange-desktop` at the root of the delivered repository. A thin Mac client may open the shared service at `ORANGE_SERVER_URL`. The same employee interface must work in a browser. The service can run separately from the Mac. Provide installation and launch instructions with the product.

For a local session the integration command is `./orange-desktop --port PORT --state DIRECTORY`. Bind to loopback, persist work under that directory, and serve your employee interface at `GET /`. Ship the server dependencies with the product or use the runtime that is already installed. The portable runtime has Python 3.13. The dev environment also has the application SDK described in [the resource inventory](README.md).

The existing workplace gateway provides employee identity through `X-Orange-Employee`. It posts normalized source events as documents arrive. Keep the most recent revision of each document, handle retries and remove retracted records from subsequent answers. The controlled workplace feed supports the same seven record types as the preloaded snapshot. We can replay changes without connecting to employees’ real accounts.

| Operation | Integration contract |
| --- | --- |
| `POST /api/events` | JSON with `op` set to `upsert` or `delete`, a source `doc_id` and a positive integer `version`. Upserts also include `source_type`, `title` and `content`. Return a successful HTTP response after the change is searchable. |
| `POST /api/work` | JSON with an `intent` of `ask`, `handoff` or `customer_reply` and the employee's `text`. Optional `destination` and `owner` carry explicit choices. Return `text` and `citations` as an array of objects with `doc_id` and `quote`. For work that creates an item also return `item` with its `id`, `text`, `destination`, `owner` and `status`. |
| `GET /api/drafts` | Return a JSON array of the work items available to the current employee. |
| `PATCH /api/drafts/ID` | Accept a replacement `text` value from an employee who may edit the item. Return the updated item on success. |
| `GET /api/outbox` | Return a JSON array of messages the employee's workspace has actually sent. During development outbound messages stay within the supplied workplace environment. |

The gateway accepts different business policies. Ask the product owner about routing, ownership, visibility and customer communications. The existing batch client contract is in [integration.md](integration.md).

/**
 * Open the screens listed in CAPTURE_PLAN (a JSON file: [{ws, urls}]) against the server at CAPTURE_URL, the way the
 * client's own smoke test does, and mark where each one starts, so a proxy can tell which requests each screen made.
 * scripts/record_live.py copies this file into the reference client's src/test for one run and removes it afterwards.
 */
import { screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";

import { routes } from "@/routes/router";

import { renderAt } from "./render";

const BASE = process.env.CAPTURE_URL;
const PLAN = process.env.CAPTURE_PLAN;
const run = BASE && PLAN ? describe : describe.skip;
const realFetch = globalThis.fetch;

run("the client's requests, screen by screen", () => {
  beforeAll(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = false;
    vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
      const { signal: _signal, ...rest } = init ?? {};
      return realFetch(`${BASE}${String(input)}`, rest);
    });
  });

  it("opens every planned screen", async () => {
    const plan = JSON.parse(readFileSync(PLAN as string, "utf8")) as Array<{ ws: string; urls: string[] }>;
    for (const { ws, urls } of plan) {
      sessionStorage.setItem(`stockwell.proxy.${ws}`, JSON.stringify("U-01"));
      for (const url of urls) {
        await realFetch(`${BASE}/__screen__?${new URLSearchParams({ ws, url })}`);
        const view = renderAt(routes, `/w/${ws}${url}`);
        try {
          await waitFor(() => expect(screen.getAllByRole("heading", { level: 1 }).length).toBeGreaterThan(0), { timeout: 8000 });
          await waitFor(
            () =>
              expect(
                screen.queryAllByRole("status", { name: "Loading" }).length + screen.queryAllByText("Loading…").length,
              ).toBe(0),
            { timeout: 8000 },
          );
          await new Promise((resolve) => setTimeout(resolve, 150));
        } catch {
          // a screen that never settles is still recorded as far as it got
        } finally {
          view.unmount();
        }
      }
      await realFetch(`${BASE}/__screen__?${new URLSearchParams({ ws, url: "(end)" })}`);
    }
  }, 7_200_000);
});

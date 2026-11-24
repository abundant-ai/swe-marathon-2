# Keep deliveries moving around closures

Keep the dispatch interface and both fleet behaviors. One of our routes can close while robots are moving. A reroutable fleet should find another available path. A fixed-loop robot must wait for its next lane to open. Other parts of the facility should keep operating while either robot waits.

Accept `closure` events with `resource`, the resource ID, and `closed`, a boolean. Closed resources cannot be acquired for a new move. An occupied robot may use a closed resource to exit it if the source holds it and the destination does not. A closure has no effect on a command already emitted. Accept any number of closures simultaneously, including reopening an already open resource.

Jobs may now have integer `priority` from 0 through 9, default 0. If two queued jobs can immediately begin on the same otherwise idle robot at the same pickup station, start the higher-priority job first and break ties by job arrival order. Keep assigned jobs with their robots. Closed routes and waiting jobs may coexist. A route robot must take an available alternative that can complete its job when the direct lane is closed. A temporary closure on an unrelated route does not suspend available jobs elsewhere.

Keep the existing response schema. Re-evaluate work on each tick as before.

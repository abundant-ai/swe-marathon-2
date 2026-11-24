# Resume after the docking process restarts

The controller can be killed after replying, or after a response was lost. Keep the existing interface. Store enough information in the supplied state directory to resume the same mission with the same configuration. New missions use an empty state directory.

Persist state before exposing the response. The transport can retransmit the latest observation with the same tick and identical fields. It must receive the identical response, including the original speeds and status, without applying the observation or counting another sample or attempt. A completed or failed mission stays terminal after restart. A retry already spent stays spent. If the process restarts while a retreat is paused, resume only when direction and odometry are again available, and keep the prior useful evidence. An observation following a retransmission has a higher tick than the previous accepted observation. There is only one process for a mission at a time.

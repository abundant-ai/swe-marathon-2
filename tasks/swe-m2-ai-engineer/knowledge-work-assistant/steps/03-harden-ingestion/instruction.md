Orange is about to receive a spike in incoming documents. Harden ingestion so it
can handle that workload while preserving the ingestion contract from the earlier
steps. Keep the assistant's existing functions and commands working, and maintain
the 95% answer accuracy target from step 2.

> Draft: The arrival rate, burst duration, document sizes, failure scenarios, and
> acceptable ingestion delay still need to be defined. Review Incident Arena's
> approach before choosing the workload and recovery checks.

# Metric contact picking from a real desk video

Reconstruct a colored metric workspace and four labeled contact surfaces from real RGB video. A downstream cursor must hit the correct surface at the measured depth. The independent check uses 400 registered rays across four annotated views. A stray labeled face can create an incorrect pick. The official reward is the lowest of contact picking, outlines, parent-object depth, and whole-scene RGB-D coverage.

Restore the qualified telephone package and apply the extension in a fresh output directory.

```sh
python3 tasks/static/ai_research/telephone-contact-reconstruction/scripts/prepare_data.py --qualified-runtime /tmp/telephone-base
python3 tasks/static/ai_research/telephone-contact-reconstruction/contact_queries/stage.py /tmp/telephone-base /tmp/contact-picking
```

## November 27 qualification

All nine matched trials produced a valid independently rebuilt mesh and a final test receipt. The three GPT-6.2-sol xhigh scores were 0, 0.028813 and 0.039604. DeepSeek-V4.1-Flash and GLM-5.3 each scored zero three times. All six swapped and absent-image GPT trials scored zero. Five rebuilt with matching receipts. One swapped submission omitted the required scene() entry point. The results establish difficulty under the allocated time. They do not demonstrate a five-day workload. [Matched trials](https://www.oddish.app/experiments/9f168289) · [Optical controls](https://www.oddish.app/experiments/15114b34)

The original matched RGB reference scored 0.5361. Improved stereo bodies and color estimation raised the hosted reference to 0.5511. Its contact-picking F1 was 0.8190, outline score 0.7688 and parent-depth F1 0.7292. Whole-scene RGB-D coverage limited the reward. The two releases differ only in three author solution files. Every candidate-visible and verifier file matches byte for byte. The inventory identifies the restored package and the trial receipts identify the exact evaluated version. [Updated reference](https://www.oddish.app/experiments/204d59c5) · [Inventories and trial receipts](qualification.json)

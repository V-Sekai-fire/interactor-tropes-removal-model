# interactor-tropes-removal-model

A pre-commit and CI gate that finds Simplified Technical English violations in prose and suggests a rewrite for each one.

## Use

The gate reads one ONNX model that scores each sentence for rule violations and a second model that writes the rewrite. It reports the file, the line, the rule and the suggestion. It checks the mechanical part of the rules only. It is not a certified checker, because some rules need a human to decide.

## Build and run

The pixi tasks in `pixi.toml` train the models and export them to ONNX. A release of this repository also carries the exported models. With the models in place, run the gate on files:

```sh
pixi run gate README.md
```

`pre-commit install` adds the gate as a hook.

## Licence

MIT. See `LICENSE`.

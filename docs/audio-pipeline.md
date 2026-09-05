# Audio Analysis Pipeline

## Architecture

The audio subsystem is a plugin-based analysis pipeline. Analyzers declare their capabilities and dependencies, register through the analyzer registry, and return typed results consumed by the pipeline and downstream DJ logic.

Optional/heavy capabilities remain isolated behind explicit dependency and runtime capability checks.

## Pipeline orchestration

```text
load audio
  → establish analysis context
  → run independent analyzers
  → merge prior results
  → run dependent analyzers
  → persist typed feature results
```

The pipeline may use staged/tiered execution. Higher-cost analysis should be requested only when the workflow needs the additional information.

Partial analyzer failures should not silently destroy usable results. Known failures remain observable through the pipeline's typed reporting/error mechanism; unexpected failures are wrapped at the pipeline boundary.

## Analysis context and reuse

Multiple analyzers that consume the same representation should reuse shared DSP state such as STFT-derived values and onset envelopes.

When parallel execution is used, sharing and caching must respect worker ownership and lifetime. Shared-memory or worker-local caches are implementation optimizations; their identities must not allow state to leak between analysis runs.

The exact analyzer inventory is runtime-derived and intentionally omitted here.

## Sampling and windowing

Analysis may use a bounded or stitched representation for expensive whole-track measurements when the algorithm permits it. Window selection and stitching must avoid introducing artificial discontinuities, false onsets, or phase artefacts that distort tempo/beat measurements.

Any sampling strategy that materially affects a feature should be covered by regression tests for boundary and seam behaviour.

## Tempo and beat correctness

Tempo and beat analysis must use a metric appropriate to the signal and the required precision. Do not use a confidence proxy that is known to saturate or an algorithm whose quantization materially distorts the desired BPM estimate.

Derived tempo-stability calculations must be robust to artefacts introduced by sampling and stitching. Outlier handling belongs in the implementation and regression tests, not in ad-hoc downstream filtering.

## Persistent analysis

Frame-level/time-series information can be stored outside the relational feature row when its volume makes that appropriate. Persistent references must carry enough metadata to identify the representation used to produce the artifact.

Deep analysis may compose stem separation, per-stem analysis, beatgrid, structural segmentation, embeddings and other expensive stages. These stages are optional heavy workflows, not implicit prerequisites for every track operation.

## Mood classification

The project uses rule-based feature-driven classification where applicable. A mood/subgenre label is a curation hint, not ground truth. When the corpus or task changes, validate that the features used by the classifier still discriminate the target data.

## Audio contracts

```python
class BaseAnalyzer(ABC):
    name: str
    capabilities: set[str]
    required_packages: list[str]

    @abstractmethod
    async def analyze(self, audio: AudioSignal) -> AnalyzerResult:
        ...

    def is_available(self) -> bool:
        ...
```

The concrete analyzer set, feature count, dependency versions, clip durations and benchmark timings belong to code/configuration or time-bounded research, not to this architecture document.

## Heavy backend discipline

Stem separation and similar DSP/ML workloads must have explicit capability detection, actionable failure handling, and bounded resource behaviour. Machine-specific memory limits, benchmark measurements and corpus statistics should live in benchmark/research material.

## Known implementation caveats

`pitch_salience_mean` is a proxy for sustained pitched content rather than a direct vocal detector. Vocal/synth discrimination must combine it with other audio evidence when the downstream decision requires that distinction.

For current implementation details, inspect `app/audio/` and its tests; this document deliberately stays at the durable architecture level.

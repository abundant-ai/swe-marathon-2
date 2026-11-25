<!-- https://doc.openfoam.com/2606/fundamentals/input-types/Function1/ -->

# Function1

## Overview

The `Function1` type provides users with a run\-time selectable option to
describe entries. The default behaviour applies a constant value, and resembles
base type entries, e.g. for a constant, scalar `Function1`:

```
myScalar        1.0;

```

This can also be written:

```
myScalar        constant 1.0;

```

## Options

The set of `Function1` types include:

* `coded`
* `constant`
* `cosine`
* `csv`
* `functionObjectTrigger`
* `functionObjectValue`
* `halfCosineRamp`
* [inputValueMapper](inputValueMapper.md)
* `linearRamp`
* `none`
* `one`
* `polynomial`
* `quadraticRamp`
* `quarterCosineRamp`
* `quarterSineRamp`
* `ramp`
* `scale`
* `sine`
* `square`
* `step`
* `table`
* `tableFile`
* `uniform`
* `zero`

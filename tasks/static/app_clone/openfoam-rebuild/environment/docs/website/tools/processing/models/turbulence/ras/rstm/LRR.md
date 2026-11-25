<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/rstm/LRR -->

# Launder, Reece and Rodi (LRR)

## Properties

* Reynolds stress model

## Model equations

## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        LRR;
}

```

## Further information

Source code:

* [Foam::RASModels::LRR](https://api.openfoam.com/2606/Foam_RASModels_LRR.html)

References:

* Standard model: *Launder et al.* [37](../../../../../../references.md#launder_progress_1975)
* Recommended generalized gradient diffusion model: *Daly and Harlow* [13](../../../../../../references.md#daly_transport_1970)
* Gibson\-Launder wall\-reflection: *Gibson and Launder* [19](../../../../../../references.md#gibson_ground_1978)

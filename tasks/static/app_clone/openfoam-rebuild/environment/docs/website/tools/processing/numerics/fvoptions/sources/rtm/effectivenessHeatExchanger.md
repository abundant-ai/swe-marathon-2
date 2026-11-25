<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/effectivenessHeatExchanger -->

# Heat exchanger

## Properties

The heat exchanger is modelled as a volumetric energy source where the energy
transfer between two fluid streams is based on an effectiveness, specified as
a function of the mass flow rates.

Qt\=e(m˙1,m˙2)(T2−T1)m˙1Cp, Q\_t \= e \\left(\\dot{m}\_1 , \\dot{m}\_2 \\right) \\left(T\_2 \- T\_1\\right) \\dot{m}\_1 C\_p,Qt​\=e(m˙1​,m˙2​)(T2​−T1​)m˙1​Cp​,
Where:

QtQ\_tQt​
: total heat source

e(m˙1,m˙2)e(\\dot{m}\_1,\\dot{m}\_2\)e(m˙1​,m˙2​)
: effectiveness table

m˙1\\dot{m}\_1m˙1​
: net mass flux entering heat exchanger \[kg/s]

m˙2\\dot{m}\_2m˙2​
: secondary mass flow rate \[kg/s]

T1T\_1T1​
: primary inlet temperature \[K]

T2T\_2T2​
: secondary inlet temperature \[K]

CpC\_pCp​
: specific heat capacity \[J/kg/K]

The energy source is distributed across the cells according to:

Qc\=Vc∣Uc∣(Tc−Tref)∑(Vc∣Uc∣(Tc−Tref)), Q\_c \= \\frac{V\_c \|U\_c\| (T\_c \- T\_{\\ref})}{\\sum(V\_c \|U\_c\| (T\_c \- T\_{\\ref}))},Qc​\=∑(Vc​∣Uc​∣(Tc​−Tref​))Vc​∣Uc​∣(Tc​−Tref​)​,
Where:

QcQ\_cQc​
: energy source for cell

VcV\_cVc​
: volume of the cell \[m3]

UcU\_cUc​
: local cell velocity \[m/s]

TcT\_cTc​
: local call temperature \[K]

TrefT\_{\\ref}Tref​
: min or max(T) in cell zone depending on the sign of QtQ\_tQt​ \[K]

Optional entries:

* `primaryInletT` : sets the primary inlet temperature. If not set, the flux\-averaged temperature is used
* `targetQdot` : the secondary inlet temperature is derived from a target heat rejection

## Usage

The option is specified using:

```
heatExchanger1
{
    type            effectivenessHeatExchanger;
    selectionMode   cellZone;
    cellZone        porosity;

    secondaryMassFlowRate   1.0;
    secondaryInletT 336;
    faceZone        facesZoneInletOriented;
    outOfBounds     clamp;
    file            "effTable";

    // Optional
    // primaryInletT 293;
    // targetQdot   1500;
}

```

The two\-dimensional effectiveness table is specified according to, e.g. for
the table

|  | mfr2,1 | mfr2,2 | mfr2,3 |
| --- | --- | --- | --- |
| mfr1,1 | A | B | C |
| mfr1,2 | D | E | F |
| mfr1,3 | G | H | I |

the equivalent entry becomes:

```
(
    (
        mfr1,1
        (
            (mfr2,1    A)
            (mfr2,2    B)
            (mfr2,3    C)
        )
    )
    (
        mfr1,2
        (
            (mfr2,1    D)
            (mfr2,2    E)
            (mfr2,3    F)
        )
    )
    (
        mfr1,3
        (
            (mfr2,1    G)
            (mfr2,2    H)
            (mfr2,3    I)
        )
    )
);

```

## Further information

Tutorials

* *none*

Source code

* [heatExchangerSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/heatExchangerSource)

**History:** Introduced in version [v3\.0\+](https://www.openfoam.com/news/main-news/openfoam-v3.0+)

<!-- https://doc.openfoam.com/2606/fundamentals/about -->

# About

Welcome to the OpenFOAM® documentation!

OpenFOAM® (for "**Open**\-source **F**ield **O**peration **A**nd **M**anipulation")
is a powerful, free and open\-source continuum mechanics software.

The main purpose of OpenFOAM® is to enable engineers, scientists, and
researchers to easily and reliably model and analyze continuum mechanics
problems in a wide range of applications. With OpenFOAM®, users can gain
valuable insights into fluid flow phenomena, optimize designs,
evaluate performance, and make informed engineering decisions.

OpenFOAM® offers a comprehensive suite of pre\-processing, processing and
post\-processing tools, and libraries for simulating diverse scenarios,
such as incompressible and compressible flows, [turbulence](../tools/processing/models/turbulence.md)
and [heat transfer](../tools/processing/models/thermophysical.md), optimisation, acoustics,
chemical reactions, solid mechanics and electromagnetics. It finds applications
in industries such as automotive, aerospace, energy, environmental engineering,
chemical processing, and academic research.

OpenFOAM®'s modular and easily extensible nature allows users to customize
and extend the software to suit their specific needs in no time. It provides a
flexible framework for implementing user\-defined models, boundary conditions,
and numerical schemes, enabling advanced and customised simulation capabilities.

OpenFOAM®'s free and open\-source nature encourages collaboration, knowledge
sharing, and innovation within its software community.
The transparency offered by OpenFOAM® allows users to see the
inner workings of the algorithms and models, providing a robust platform for
development and collaborative research.
OpenFOAM® empowers its users to contribute to the software's development,
improve its functionality, and benefit from the collective expertise of the
community.

OpenFOAM® is programmed in [C\+\+](https://isocpp.org/), using the
[GNU GLP3 license](https://www.gnu.org/licenses/gpl-3.0.en.html).
This license guarantees the open sourceness of the project while
allowing private and commercial usage. OpenFOAM® is publicly hosted in
[GitLab](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/)
and is actively maintained and developed by [OpenCFD Ltd.](https://www.openfoam.com).

In OpenFOAM®, complex concepts can be written in a familiar fashion.
For example, systems of equations are implemented using a syntax that closely
follows the mathematical notation, e.g.:

Time rate of change \| ∂∂t(ϕ)\\ddt{\\phi}∂t∂​(ϕ) \| `fvc::ddt(phi)`
Gradient \| ∇ϕ\\grad \\phi∇ϕ \| `fvc::grad(phi)`
Divergence \| ∇ ∙ ϕ\\div \\phi∇∙ϕ \| `fvc::div(phi)`
Laplacian \| ∇2ϕ\\laplacian \\phi∇2ϕ \| `fvc::laplacian(phi)`
Linearised sources \| sϕs \\phisϕ \| `fvc::Sp(s,phi)`

This abstraction permits complex equations to be written concisely in a
human\-readable form, e.g. the transport equation to evolve the P\-1 radiation
model:

∇ ∙ (Γ∇G)−aG\=−4ϵσT4−E \\div \\left( \\Gamma \\grad G \\right) \- a G \= \-4 \\epsilon \\sigma T^4 \- E∇∙(Γ∇G)−aG\=−4ϵσT4−E
is represented by the code:

```
// Solve G transport equation
solve
(
    fvm::laplacian(gamma, G_)
  - fvm::Sp(a_, G_)
  ==
  - 4.0*(e_*physicoChemical::sigma*pow4(T_)) - E_
);

```

These examples make use of explicit operations using *Finite Volume Calculus*,
represented by the `fvc::` prefix, where implicit terms are represented
analogously using the *Finite Volume Method* `fvm::` form. For more
information, please see [Numerics](../tools/processing/numerics.md).

Many pre\-built applications are supplied ready\-to\-use complete with a
[tutorial suite](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials) to showcase functionality.

<!-- https://doc.openfoam.com/2606/fundamentals/input-types/expression-syntax -->

# Expressions

## Expressions syntax

The *Expressions* syntax enables users to define custom expressions for use in
a variety of scenarios, including:

* input dictionaries
* boundary conditions
* utilities, e.g. setting field values

The following sections describe how to write the expressions and provide an
overview of the range of functionality.

## Terminology

The term *expressions* implies the interpretation of ***string\-like***
input as various types of mathematical or field evaluations within
OpenFOAM itself. For example, to use the following *string* input in
a dictionary as a mathematical evaluation (after substitution of the
dictionary variables):

```
xpos #eval "$radius * sin(degToRad($angle))";

```

Alternatively, to use the following *string* input to define a volume\-field
evaluation:

```
"alpha.air * mag(rho * U)"

```

The *expressions* do not use dynamically compiled C\+\+\-code to solve
the problem, but instead rely upon predefined *grammar* rules and
parsing operations for the evaluation.
The entire evaluation is called a *parse* or *parser* operation,
although it strictly speaking comprises three components:

1. The ***scanner***, which splits the string input into individual
input tokens such function names, operators, numbers etc.
2. The *grammar* ***parser***, which handles the relationships between
the tokenized components. This is the part that allows for
mathematical relationships such as addition, subtraction,
and handles operator precedence etc.
3. The parse ***driver*** acts as an intermediate for the scanner and
grammar parser when retrieving or storing OpenFOAM fields, or
obtaining mesh\-relevant quantities such as cell centres etc. It
will also be the entity that holds the final result of the
evaluation.

For most purposes the distinction between the sub\-components can be
safely ignored and the entirety simply called the ***parser***.

However, as the first examples illustrate, a *parser* is domain\-specific
and there will be different types of parsers for different applications.
Currently these are the following:

* `fieldExpr` : a general mathematical and ***field*** expression parser
for primitive fields such as `scalarField`, `vectorField`, but not
associated with any geometric fields or mesh geometry. For a field
size of `1` this corresponds to a mathematical (non\-field)
expression evaluation.
* `patchExpr` : expression evaluation on ***patches***.
Use face values for its *native* structure, with the possibility
of accessing point values.

## Expression Grammar

The basic syntax of the *expressions* largely resembles that of the
OpenFOAM source code:

* the syntax is C\+\+\-like
* C/C\+\+ comments are supported
* the usual operator precedence rules apply
* uses OpenFOAM operator overloads wherever possible.
This means, for example, that scalar\-vector multiplication works
as expected.
* uses standard and OpenFOAM function names e.g. `sqrt()`, `mag()`,
`magSqr()` wherever possible.

### Comments

Since *expressions* may easily grow in complexity, internal documentation
of expressions is encouraged in the form of C/C\+\+ style comments internal
to the expression. For example,

```
condition
#{
    // Limit to distances within the given radius
    (mag(pos() - centre) < (1.01 * radius) /* 1% safety margin */ )

    // and for +ve Y-direction
  && bool(pos0((pos() - centre).y()))
#};

```

### Macros

There is no support for macros, but since the *expression* is
generally passed through dictionary expansion prior to evaluation,
dictionary substitutions can be used. For example,

```
radius  0.05;
radius  #eval{ 1.01 * $radius };
centre  vector (0, 0, #eval{ sqrt($radius) });
offset  (pos() - $centre);

condition
#{
    (mag($offset) < $radius)
  && bool(pos0($offset).y())
#};

```

More advanced information about macro or dictionary substitutions is
provided in later sections.

### Operators

The usual [precedence\-rules](https://en.cppreference.com/w/cpp/language/operator_precedence)
apply:

* `+ - * /` : Arithmetic operations
* `&` : Inner product for vectors and tensors
* `^` : Cross product of two vectors
* `%` : Modulo operator
* `&& ||` : The logical *and* and *or* operators
* `-` : Unary negation
* `!` : Logical negation
* `< > >= <=` : Relational comparisons
* `== !=` : : Equality and inequality\-operators
* `?` and `:` : Ternary operator for `cond ? a : b`.
The condition must evaluate to bool, the fields `a` and `b`
must be of the same type.

### Identifiers

When field or variable names are referenced, the identifiers are
similar to C\+\+ requirements (alphanumeric with underscores) but the
dot (`.`) character is also permitted when it does not appear at the
start of the name.

General punctuation\-like characters that are occasionally used in
OpenFOAM fields, e.g. the `-` or `:` characters, cannot be used
directly as identifiers, but require quoting of the entire identifier.

* Single/double quotes are used to support arbitrary characters in an
identifier. For example, `"sin(angle)"` and `"field:a-b"` would be
treated as single identifiers, even if they would otherwise appear
to be expressions.

Note that there is no semantic difference between single and
double quotes, but they must be used consistently for quoting an
individual element, i.e.,

```
// Good quoting!
pos("alpha.x") * 0.4*neg('alpha.xx')

// Bad quoting!?!
pos("alpha.x') * 0.4*neg('alpha.xx")

```

### Data Types

The *expressions* support the familiar OpenFOAM data types:

* **scalar** : floating point values, scalar fields
* **vector** : vector fields or x\-y\-z positions
* **tensor** : tensor fields (3 x 3\) components
* **symmTensor** : a six\-component symmetrical tensor
* **sphericalTensor** : a single component spherical tensor
* **bool** : a boolean field result of logical operations.
For some parsers, e.g., `volumeExpr` an internal representation
as **scalar** (0,1\) may be used.

Since operations with fields of integers are not intrinsic to
OpenFOAM, they are not supported in *expressions* either; here
**scalar** types should be used instead. If incompatible operations
are specified within an expression the parser will issue an error
message during the evaluation. Examples of incompatible operations:

* **scalar** \+ **vector**
* sqrt(**vector**)

For example,

```
Syntax error in expression at position:18
<<<<
sqrt(vector(1,2,3)) * 10
                 ^^^^ near here
>>>>

```

The syntax error only appears after the *vector* composition has
finalized and the parser determines that the parameter for `sqrt` is
not valid. Users may initially find the location of the error slightly
odd and/or difficult to interpret, but a second *valid*
example helps illustrate why this error location was correct:

```
sqrt(vector(1,2,3) & vector(1,1,1)) * 10

```

Here the expressions continues on with a dot\-product `&` followed by
another vector composition. The parser can now continue and
reduces this to a scalar, which is a valid parameter for `sqrt`.

The return type of the expression result is a polymorphic data type,
which means that its type is only known after the evaluation has
completed. If this does not match the expected type, it will generate
a runtime error only *after* the expression has been evaluated.

### Constants

Numeric constants are written in regular C\+\+/OpenFOAM forms. For
example, `42`, `3.1415`, `6.66e2` etc. However, just like with OpenFOAM
dictionary syntax, numbers with a leading positive sign are not supported.
So `42.0` and `-42.0` are valid, but `+42.0` is not.

Named constants resemble functions:

* `pi()` : 3\.14159\...
* `degToRad()` : same as `pi() / 180` but as a pre\-calculated value
* `radToDeg()` : same as `180 / pi()` but as a pre\-calculated value
* `time()` : the current simulation time\-value (if used by the parser)

This form makes it easier to reuse constants as unary functions. For
example, the function `degToRad()` can be used with or without
arguments such that both `sin(degToRad(45))` and `sin(45*degToRad())`
will produce the expected result.

There are a few literals used as constants as well:

* `true`, `false` : for boolean values
* `tensor::I` : is the unit tensor
* `Zero` : equivalent to the `Foam::zero` constant

### Composing data types

As previously mentioned, *expressions* can handle different data
types, but unlike C\+\+ code we lack regular means of declaring the types.
Instead a *composition* syntax is used to define all non\-scalar types.

#### Vectors

Vector values can be constructed using the keyword `vector` and
three scalar values or scalar fields. These scalars can be constants or
sub\-expressions that yield scalars.
For example,

```
vector(1,2,3)

vector(1,pos().y(),0)

vector(10, 34/8, 5*magSqr(pos().y()))

```

#### Tensors

Tensors are constructed with the keyword `tensor` and 9 scalar
values for the components.

#### Symmetric tensors

Symmetric tensors are constructed using the keyword `symmTensor`
and 6 components (`xx`, `xy`, `xz`, `yy`, `yz`, `zz`).

#### Spherical tensors

Spherical tensors are constructed using `sphericalTensor` and a single
scalar component.

#### Boolean

Boolean fields are somewhat special since they are normally the result
of some logical operation and are not defined directly. However, the
keyword `bool` can be used to force a boolean conversion of scalar
values. A threshold of \-/\+ 0\.5 is used to define true/false. This
definition is generous but works well under the assumption that
scalars values (0,1\) correspond to the truth values and allows for any
rounding or interpolation effects. This also yields good
characteristics when integer calculations have been performed with
scalars. Some examples,

```
bool(-10)     ==> true
bool(-0.4)    ==> false
bool(0.4)     ==> false

```

For some cases the `bool` keyword can makes expressions a bit easier to
understand. For example,

```
bool(pos(x))

```

versus

```
(pos(x) > 0.5)

```

### Decomposing data types

It is also possible to extract sub\-components from more complex data
types with component `.` methods.
For example, the expression `U.x()` returns the X\-component of the `U` field.

| Input Data Type | Component methods | Output data type |
| --- | --- | --- |
| vector | x y z | scalar |
| tensor | xx xy xz yx yy yz zx zy zz | scalar |
| symmTensor | xx xy xz yy yz zz | scalar |
| sphericalTensor | ii | scalar |

The same `.` method syntax is used for tensor transpose, or extracting
of vectors from tensors:

| Input Data Type | Component methods | Output data type |
| --- | --- | --- |
| tensor | x y z | vector (the corresponding rows) |
| tensor | diag | vector (the diagonal) |
| tensor | T | tensor (transpose) |
| symmTensor | diag | vector (the diagonal) |
| symmTensor | T | symmTensor (transpose is a no\-op) |
| sphericalTensor | T | sphericalTensor (transpose is a no\-op) |

#### Naming ambiguities

Since a dot (`.`) can appear in a variable name, some ambiguity in the
intended meaning of the input can arise. For example, the text `U.x`
could be the field `U.x`, but potentially could also be leading into
the expression `U.x()` \- ie, the x\-component of the `U` field.

The parser heuristics resolves this with the following approach:

* first attempt to resolve in favour of the longest match, e.g. the
field `U.x`.
* if the longest match fails, check if the dot ending corresponds to
a known method name (eg, `x`, `xy`, but not `air`) and attempt to
resolve with the shortened field name (Eg, `U`).
* if both possibilities fail, give up.

This approach masters most the fields from most simulations without
any problem. It is fairly rare that a simulation would have both a `U`
vector field and a `U.x` scalar field. If however such a situation
does arise, it is simple to resolve with some direction from the user:

* introduce additional elements such as spacing or brackets
to separate the ambiguous elements.
Eg, `U .x()` or `(U).x()`
* quote the field names to suppress interpretation.
Eg, `"U.x"`, `'U.x'` or even `"U".x()`

### Mathematical functions

Many typical OpenFOAM mathematical functions are implemented:

* **mag(x)** : Absolute value `|x|`
Implemented for all data types. Yields a scalar.
Can be also be used to convert a bool to a scalar.
* **magSqr(x)** : Square of the magnitude `|x|^2`
Implemented for all non\-logical data types. Yields a scalar

The following functions only work for scalars:

* **pow(x,y)** : Power `x^y`
* **exp(x)** : Exponential function `e^x`
* **log(x)** : Natural logarithm
* **log10(x)** : Logarithm base 10
* **sin, cos, tan** : Usual trigonometric functions
* **asin, acos, atan, atan2** : Inverse trigonometric functions
* **hypot** : Hypotenuse `sqrt(x^2, y^2)`
* **sinh, cosh, tanh** : Hyperbolic functions
* **asinh, acosh, atanh** : Inverse hyperbolic functions
* **sqr(x)** : Square `x^2`
* **sqrt(x)** : Square root `sqrt(x)`
* **cbrt(x)** : Cubic root `cbrt(x)`
* **floor(x)** : Round down `floor(x)`
* **ceil(x)** : Round up `ceil(x)`
* **round(x)** : Round closest `ceil(x)`

These functions depend on the sign of a scalar:

* **pos(x)** : if `x` greater zero: 1\.0 else 0\.0
* **pos0(x)** : if `x` greater\-equal zero: 1\.0 else 0\.0
* **neg(x)** : if `x` less zero: 1\.0 else 0\.0
* **neg0(x)** : if `x` less\-equal zero: 1\.0 else 0\.0
* **sign(x)** : if `x` is positive: 1\.0 else if `x` is negative: \-1\.0

These functions act as global reduction operations and return a single
value across all processors:

* **min(..)** : global minimum of the field
* **max(..)** : global maximum of the field
* **sum(..)** : the global sum of all values
* **average(..)** : the global average of the field

The binary forms of **min(x,y)** and **max(x,y)** process and return
fields.

There is also some support for random numbers.

* **rand()** : A uniformly distributed random number on the interval
(0\-1\) using the default seed value.
* **rand(NUM)** : Like `rand()` but using the integer value `NUM` for
its seed.

When the *parser* is associated with a mesh, the current time index is
added to the seed so that the random distribution is different at each
time\-step but still reproducible.

## Domain\-specific parsers

The supported syntax described thus far as been general and common to
all parsers. However, there are different
expression parsers depending on where they can be applied.
The function `vol()`, for example, is only appropriate for a
volume\-domain parser where a cell volume is actually meaningful.

To aid with keeping track of the capabilities, we assign some keys to
the domains:

| Key | Name | Description |
| --- | --- | --- |
| X | `fieldExpr` | general purpose, such as used in dictionary `#eval` expressions. |
| P | `patchExpr` | expression evaluation on ***patches*** |
| V | `volumeExpr` | expression evaluation on mesh internal/***volume*** |

It also also useful to reiterate an earlier point about the
domain\-specific parsers. These will have a natural or *native*
structure used for field access, and may have secondary field types.
This means that function such as `pos()` for mesh positions will mean
different things in different domains. For a ***patch*** parser this
corresponds to face centres, for a ***volume*** parser this
corresponds to cell centres.

* `patchExpr` : Uses faces for its *native* structure with points
for its secondary structure.
* `volumeExpr` : Uses cells for its *native* structure, with surfaces
or points for its secondary structure.

### Information about the mesh

Functions that provide information about the mesh and are used without
any arguments:

| Function | Domain(s) | Description |
| --- | --- | --- |
| `pos()` | P, V | Native positions (P: face centres, V: cell centres) |
| `pts()` | P, V | Point positions (P: face points, V: mesh points) |
| `fpos()` | V | The face centres |
| `area()` | P, V | The face area magnitudes |
| `face()` | P, V | The face areaNormal vectors |
| `vol()` | V | The cell volumes |

These functions are only available for the ***volume*** parser. They
return a boolean field that identifies which cells/faces/points belong
to the corresponding set or zone.

| Function | Domain(s) | Description |
| --- | --- | --- |
| `cset(NAME)` | V | Logical volume field corresponding to cellSet |
| `fset(NAME)` | V | Logical surface field corresponding to faceSet |
| `pset(NAME)` | V | Logical point field corresponding to pointSet |
| `czone(NAME)` | V | Logical volume field corresponding to cellZone |
| `fzone(NAME)` | V | Logical surface field corresponding to faceZone |
| `pzone(NAME)` | V | Logical point field corresponding to pointZone |

### Mesh\-based operations

These functions incorporate domain\-specific information.

| Function | Domain(s) | Description |
| --- | --- | --- |
| `weightAverage(..)` | P, V | Area or volume weighted average (global) |
| `weightSum(..)` | P, V | Area or volume weighted sum (global) |

The weighted functions select the correct weighting according to the
context (volume or area). If given a point field, they revert to
simple, unweighted versions of `average` or `sum`.

### Interpolation or change of structure

The functions support changing or interpolating between the *native*
domain structure and the secondary structures. For example, in the
***volume*** parser, a plain number (eg, `42`) or a constant (eg,
`true`) is taken as a volume quantity. However, we may wish to have
that constant value interpreted as a face or point value instead.

| Function | Domain(s) | Description |
| --- | --- | --- |
| `face(..)` | V | A surface\-field face value |
| `point(..)` | P, V | A point\-field point value |

Additionally, we can change (interpolate) between structures.

| Function | Domain(s) | Description |
| --- | --- | --- |
| `faceToPoint(..)` | P | Interpolate face values onto points |
| `pointToFace(..)` | P | Interpolate point values onto faces |
| `cellToFace(..)` | V | Interpolate cell values onto faces |
| `cellToPoint(..)` | V | Interpolate cell values onto points |
| `pointToCell(..)` | V | Interpolate point values onto cells |
| `reconstruct(..)` | V | Reconstruct cell vector from surface scalar |

## Variables and fields

An essential point for domain\-specific parsers is how OpenFOAM fields
are accessed.

Any identifier that is not a function defined in the grammar is taken
to be the name of an internal *variable* (searched first) or an
OpenFOAM *field* (searched second). The only exception to this rule is
for sets/zones. The parser takes note when `cset(..)`, `fzone(..)` etc
functions have been seen and ensures that the following identifier is
interpreted appropriately (as the name of the set/zone).

Since variables are searched for first, they can inadvertent *shadow*
field names (eg, a variable called "rho" that effectively hides the
OpenFOAM "rho" field). By default these will be detected and flagged
as an error.

### Fields

Registered fields are found via objectRegistry lookup. For some utilities,
a mechanism similar to IOobjectList is used to locate these fields
on disk.

With this knowledge we can understand how the following (volume) expression
would be seen by the parser

```
pos(U.x()) * pos()

```

* The first `pos(..)` is the unary function for greater\-than 0\.
Operates on a scalar.
* The `U.x` appears to be a variable or field. But since `U.x` does not
exist, backtracking finds that it can resolve this as a `U` field
followed by a `.x` for the scalar component access. The following
`()` pair completes the operation and the X\-component of `U` is
extracted.
* The first `pos(..)` now completes and yields a 0/1 scalar field for
the X\-component of `U`.
* The second `pos()` is without an argument, which returns the cell
centres, to be multiplied by the previous scalar field.

### Variables

The term *variables* in the context of *expressions* denotes
intermediate values that are accessible by name and normally stored in
memory within the scope of the current domain parser. In some cases,
variables may be unnecessary and dictionary substitution combined with
inline evaluation suffices. In other cases, internally managed
variables can provide better functionality and data encapsulation. We
limit the description to regular *variables* only.

#### Variable specification

Variables are specified by the optional dictionary entry `variables`.
The entry is a list of strings, of the following form:

```
variables
(
    "varName1 = expression1"
    "varName2 = expression2"
    ...
);

```

These specify that the results of the expressions be saved with the
respective names. The evaluation of the expressions uses the current
parser and the entire field is saved for further use.

The variables are evaluated in the order of appearance and can be
reused within the list (allows for intermediate variables). Once
defined, there is no mechanism to undefine a variable.

It is also possible to define a variable within the *current* context
based on an evaluation from a different domain parser or context. This
is triggered by the presence of a `{}` qualifier for the variable name:

```
   varName{parser'name/region} = expression

```

This means that `expression` is evaluated with the parser
specified between `{}`. The form shown above is the most general.

The value of `parser` is one of the defined domain parsers (`patch` or
`volume`). The `name` selects the concrete entity the parser should
work on (for instance the patch name). Since patch references are the
most common, this can be omitted and the specification of the patch
name alone is sufficient:

```
varName{patchName} = expression

```

which evaluates the `expression` on patch `patchName`.

In general, these external expressions are only meaningful when the
the expression yields a uniform value (eg, a sum or average) since
there is no other reasonable means to map or interpolate values from
different types of entities, or entities with different sizes or
locations. So if the expression yields a non\-uniform value, a warning
will be emitted and the average used.

Here is a further example of variable definitions:

```
variables
(
    #{ tempK = weightedSum(rho * T) / weightedSum('rho') #}
    #{ pInlet{inlet} = weightedAverage(p) #}
);

```

The additional internal quoting is for illustrative purposes.

When used within expressions, the variable names are used *without*
the qualifiers used in their declaration. For example,

```
pos(p - pInlet)

```

Where `p` is the pressure *field* and `pInlet` is the *variable*
previously defined as the average pressure at the `inlet` patch.

## Macro expansion

Before expression and variable strings are used, they are expanded in
two different ways:

* the regular OpenFOAM string expansion mechanism
* a special\-purpose expansion mechanism

The additional special\-purpose expansion is unfortunately necessary to
deal with translating dictionary input into a form that is suitable
for evaluation. The mechanism is typically triggered by
`$[(cast)...]` content.

For example, given the following dictionary entry:

```
   location    (1 2 3);

```

a regular dictionary substitution:

```
mag($location)

```

produces an expression that cannot be parsed:

```
mag((1 2 3));

```

To obtain the desired expansion, we resort to using the special expansion
with a *casting* operation:

```
mag($[(vector) location])

```

which produces an expression that can be parsed:

```
mag(vector(1,2,3));

```

The additional embedded `(vector)` cast introduce the necessary
`vector` composition keyword and also ensured that the vector
components are separated with commas instead of spaces.

One additional remaining macro pasting is the `#spec;` handling
while reading `variable` lists.

If a variable list element contains `#spec;` then that is searched for
in the dictionary, interpreted as a variable list and inserted into
the variable list. During this process other lists are recursively inserted
and `$` macros are expanded.

## Further information

The Expressions functionality is a re\-implementation of `swak4Foam`
[code and ideas](https://openfoamwiki.net/index.php/Contrib/swak4Foam),
created by Bernhard Gschaider. Many thanks to him for many fruitful discussions
leading to the release of the current functionality.

**History:** Introduced in version [v1912](https://www.openfoam.com/news/main-news/openfoam-v1912)

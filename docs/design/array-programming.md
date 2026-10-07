# Array programming proposal

Status: historical design proposal, not implemented syntax or an approval to
implement these APIs. Moved from section 9 of [SPEC.md](../SPEC.md) on
2026-10-07. The section below preserves that source text and its numbering.
Its references to `docs/STATUS.md` use the repository-root path.

The [decision ledger](../plan/decisions.md) governs approval. L8 permits
accelerator interface design and L11 records tensor formats. They do not
qualify hardware targets or approve every spelling below. Array broadcasting,
tensor operators, automatic differentiation, GPU movement, and the proposed
annotations have no current language implementation. Fixed arrays and their
supported operators remain in [the type reference](../SPEC.md#33-composite-types).

Examples below are design sketches. They may use invalid A7 syntax, unavailable
functions, or types that the compiler does not provide. Check
[current status](../STATUS.md) for implemented behavior.

## Preserved specification text

## 9. Planned Array Programming for AI

### 9.1 Multidimensional Arrays

This section is a design target, not current implementation status. Tensor
types, broadcasting, vectorized tensor operators, AI primitives, GPU movement,
and performance annotations are not implemented yet. Current release status is
tracked in `docs/STATUS.md`.

#### Tensor Types
```a7
// N-dimensional tensors (up to 8 dimensions)
Tensor :: struct($T: Numeric, $N: u8) {
    data: ref T              // Flat data storage
    shape: [N]usize         // Dimensions
    strides: [N]usize       // Memory strides
}

// Type aliases for common tensor shapes
Vector :: [N]$T             // 1D vector
Matrix :: [M][N]$T          // 2D matrix
Tensor3D :: [D][H][W]$T     // 3D tensor
Tensor4D :: [B][C][H][W]$T  // 4D tensor (batch, channels, height, width)

// Dynamic tensors with runtime shape
DynTensor :: struct($T: Numeric) {
    data: ref T
    shape: []usize
    strides: []usize
    ndim: u8
}
```

#### Array Literals and Initialization
```a7
// Multi-dimensional array literals
matrix := [[1, 2, 3],
           [4, 5, 6],
           [7, 8, 9]]

// Tensor initialization with shape inference
tensor := [[[1, 2], [3, 4]],
           [[5, 6], [7, 8]]]  // Shape: [2, 2, 2]

// Explicit tensor creation
zeros := tensor_zeros([3, 4, 5], f32)     // All zeros
ones := tensor_ones([2, 3], i32)          // All ones
range := tensor_range(0, 100, [10, 10])   // Sequential values
random := tensor_random([5, 5], f32)      // Random values [0, 1)

// Tensor from data with explicit shape
data := [1, 2, 3, 4, 5, 6]
reshaped := tensor_from_data(data, [2, 3])
```

### 9.2 Broadcasting and Vectorized Operations

#### Automatic Broadcasting
```a7
// Broadcasting follows NumPy-compatible rules
a := [[1, 2, 3],        // Shape: [2, 3]
      [4, 5, 6]]

b := [10, 20, 30]       // Shape: [3] -> broadcasts to [1, 3]

result := a + b         // Element-wise addition with broadcasting
// result = [[11, 22, 33],
//           [14, 25, 36]]

// Scalar broadcasting
scaled := a * 2.0       // Multiply all elements by 2

// Complex broadcasting
x := tensor_ones([3, 1, 4])    // Shape: [3, 1, 4]
y := tensor_ones([5, 1])       // Shape: [5, 1]
z := x + y                     // Result shape: [3, 5, 4]
```

#### Vectorized Operations
```a7
// Element-wise operations (all support broadcasting)
sum := a + b           // Addition
diff := a - b          // Subtraction
prod := a * b          // Multiplication
quot := a / b          // Division
power := a ^ b         // Power
mod := a % b           // Modulo

// Mathematical functions (vectorized)
roots := sqrt(a)       // Square root of each element
logs := log(a)         // Natural logarithm
exps := exp(a)         // Exponential
sins := sin(a)         // Sine function
tans := tanh(a)        // Hyperbolic tangent

// Comparison operations (return boolean tensors)
gt := a > b            // Greater than
eq := a == b           // Equality
mask := a >= 0.5       // Create boolean mask

// Boolean operations on tensors
result := tensor_where(mask, a, b)  // Select elements based on condition
```

### 9.3 Tensor Manipulation and Reshaping

#### Shape Operations
```a7
// Get tensor properties
dims := tensor_shape(a)        // Returns [usize] of dimensions
ndim := tensor_ndim(a)         // Number of dimensions
size := tensor_size(a)         // Total number of elements
dtype := tensor_dtype(a)       // Element type

// Reshaping (must preserve total size)
reshaped := tensor_reshape(a, [6])        // Flatten to 1D
matrix := tensor_reshape(a, [2, 3])       // 2x3 matrix
tensor3d := tensor_reshape(a, [1, 2, 3])  // Add batch dimension

// View operations (share memory)
flattened := tensor_flatten(a)            // 1D view
view := tensor_view(a, [start..end])      // Slice view
```

#### Axis Operations
```a7
// Reorder dimensions
transposed := tensor_transpose(matrix)              // 2D transpose
swapped := tensor_transpose(tensor, [2, 0, 1])     // Reorder axes

// Add/remove dimensions
expanded := tensor_expand_dims(a, axis: 1)         // Add dimension at axis 1
squeezed := tensor_squeeze(a)                      // Remove size-1 dimensions
unsqueezed := tensor_unsqueeze(a, axis: 0)         // Add dimension at axis 0

// Concatenation and splitting
concat := tensor_concat([a, b, c], axis: 0)        // Join along axis
chunks := tensor_split(a, sections: 3, axis: 1)    // Split into 3 parts
stacked := tensor_stack([a, b, c], axis: 2)        // Stack along new axis
```

### 9.4 Reduction Operations

```a7
// Aggregation along axes
sum_all := tensor_sum(a)                    // Sum all elements
sum_axis := tensor_sum(a, axis: 1)          // Sum along axis 1
mean_val := tensor_mean(a, axis: [0, 1])    // Mean along multiple axes

// Statistical operations
max_val := tensor_max(a)                    // Maximum value
min_val := tensor_min(a)                    // Minimum value
std_dev := tensor_std(a, axis: 0)           // Standard deviation
variance := tensor_var(a)                   // Variance

// Find operations
argmax := tensor_argmax(a, axis: 1)         // Indices of maximum values
argmin := tensor_argmin(a)                  // Index of global minimum
```

### 9.5 Linear Algebra Operations

```a7
// Matrix operations
product := tensor_matmul(A, B)              // Matrix multiplication
dot_prod := tensor_dot(x, y)                // Vector dot product
cross := tensor_cross(u, v)                 // Cross product (3D vectors)

// Decompositions and factorizations
eigenvals, eigenvecs := tensor_eig(A)       // Eigendecomposition
U, S, Vt := tensor_svd(A)                  // Singular value decomposition
Q, R := tensor_qr(A)                       // QR decomposition
L, U := tensor_lu(A)                       // LU decomposition

// Matrix properties
det := tensor_det(A)                        // Determinant
trace := tensor_trace(A)                    // Trace
inv := tensor_inv(A)                        // Matrix inverse
norm := tensor_norm(x, p: 2)                // L2 norm
```

### 9.6 AI-Specific Operations

#### Neural Network Primitives
```a7
// Convolution operations
conv_out := tensor_conv2d(input, kernel,    // 2D convolution
                         stride: [1, 1],
                         padding: [0, 0])

pool_out := tensor_maxpool2d(input,         // Max pooling
                            kernel_size: [2, 2],
                            stride: [2, 2])

// Activation functions (vectorized)
relu := tensor_relu(x)                      // ReLU activation
sigmoid := tensor_sigmoid(x)                // Sigmoid activation
softmax := tensor_softmax(x, axis: -1)      // Softmax normalization
gelu := tensor_gelu(x)                      // GELU activation

// Normalization
batch_norm := tensor_batch_norm(x, gamma, beta, mean, var)
layer_norm := tensor_layer_norm(x, axis: -1)
```

#### Gradient Operations
```a7
// Automatic differentiation support
grad_fn := tensor_grad_enable(x)            // Enable gradient tracking
grad := tensor_backward(loss)               // Compute gradients
no_grad := tensor_no_grad { ... }           // Disable gradient computation

// Gradient clipping
clipped := tensor_clip_grad_norm(params, max_norm: 1.0)
```

### 9.7 Memory Layout and Performance

#### Memory Layout Control
```a7
// Specify memory layout
row_major := tensor_c_layout(data, shape)   // C-style (row-major)
col_major := tensor_f_layout(data, shape)   // Fortran-style (column-major)
strided := tensor_strided(data, shape, strides)

// Memory management
contiguous := tensor_contiguous(a)          // Ensure contiguous memory
copied := tensor_copy(a)                    // Deep copy
cloned := tensor_clone(a)                   // Clone with same layout
```

#### Performance Annotations
```a7
// Compiler hints for optimization
@vectorize                                  // Enable SIMD vectorization
tensor_operation :: fn(a: Tensor, b: Tensor) Tensor {
    ret a + b
}

@parallel                                   // Enable parallel execution
matrix_multiply :: fn(A: Matrix, B: Matrix) Matrix {
    ret tensor_matmul(A, B)
}

// Memory prefetch hints
@prefetch(a.data, size_of(f32) * tensor_size(a))
result := expensive_computation(a)
```

### 9.8 Indexing and Slicing

#### Advanced Indexing
```a7
// Multi-dimensional indexing
element := tensor[i, j, k]                  // Direct element access
row := tensor[i, ..]                        // Entire row
col := tensor[.., j]                        // Entire column
block := tensor[i..i+3, j..j+3]             // 3x3 block

// Boolean indexing
mask := tensor > 0.5                        // Boolean mask
filtered := tensor[mask]                    // Elements where mask is true

// Integer array indexing
indices := [0, 2, 4, 6]
selected := tensor[indices]                 // Select specific indices

// Fancy indexing with multiple arrays
row_idx := [0, 1, 2]
col_idx := [1, 2, 0]
elements := tensor[row_idx, col_idx]        // Select (0,1), (1,2), (2,0)
```

### 9.9 Built-in Tensor Functions

```a7
// Creation functions
tensor_zeros :: fn(shape: []usize, $T: Numeric) Tensor(T)
tensor_ones :: fn(shape: []usize, $T: Numeric) Tensor(T)
tensor_eye :: fn(n: usize, $T: Numeric) Tensor(T)           // Identity matrix
tensor_arange :: fn(start: $T, stop: $T, step: $T) Tensor(T)
tensor_linspace :: fn(start: $T, stop: $T, num: usize) Tensor(T)

// Type conversion
tensor_cast :: fn($T, $U: Numeric, tensor: Tensor(T)) Tensor(U)
tensor_to_f32 :: fn(tensor: Tensor) Tensor(f32)
tensor_to_i32 :: fn(tensor: Tensor) Tensor(i32)

// I/O operations
tensor_save :: fn(tensor: Tensor, filename: string) bool
tensor_load :: fn(filename: string, $T: Numeric) Tensor(T)
tensor_print :: fn(tensor: Tensor, precision: u8)

// Device operations (for GPU/accelerator support)
tensor_to_gpu :: fn(tensor: Tensor) Tensor
tensor_to_cpu :: fn(tensor: Tensor) Tensor
tensor_device :: fn(tensor: Tensor) Device
```

### 9.10 Array Programming Examples

#### Machine Learning Example
```a7
// Simple neural network layer
Layer :: struct {
    weights: Matrix(f32)
    bias: Vector(f32)
}

forward :: fn(layer: Layer, input: Matrix(f32)) Matrix(f32) {
    // Matrix multiplication + bias + activation
    linear := tensor_matmul(input, layer.weights) + layer.bias
    ret tensor_relu(linear)
}

// Batch processing
process_batch :: fn(data: Tensor4D(f32)) Tensor4D(f32) {
    // Normalize batch
    normalized := tensor_batch_norm(data)

    // Apply convolution
    conv_out := tensor_conv2d(normalized, kernel)

    // Pooling
    ret tensor_maxpool2d(conv_out, kernel_size: [2, 2])
}
```

#### Scientific Computing Example
```a7
// Solve linear system Ax = b using tensor operations
solve_linear :: fn(A: Matrix(f64), b: Vector(f64)) Vector(f64) {
    // LU decomposition
    L, U, P := tensor_lu_pivot(A)

    // Forward substitution: Ly = Pb
    Pb := tensor_matmul(P, b)
    y := tensor_forward_solve(L, Pb)

    // Backward substitution: Ux = y
    ret tensor_backward_solve(U, y)
}

// Numerical integration using broadcasting
integrate_2d :: fn(f: fn(f64, f64) f64, bounds: [4]f64, steps: [2]usize) f64 {
    x := tensor_linspace(bounds[0], bounds[1], steps[0])
    y := tensor_linspace(bounds[2], bounds[3], steps[1])

    // Create meshgrid using broadcasting
    X := tensor_expand_dims(x, axis: 1)     // [n, 1]
    Y := tensor_expand_dims(y, axis: 0)     // [1, m]

    // Evaluate function on grid (broadcasts to [n, m])
    Z := f(X, Y)

    // Numerical integration using trapezoidal rule
    dx := (bounds[1] - bounds[0]) / cast(f64, steps[0] - 1)
    dy := (bounds[3] - bounds[2]) / cast(f64, steps[1] - 1)

    ret tensor_sum(Z) * dx * dy
}
```

---

#include "shapes.hpp"
#include <cmath>

double Circle::area() const {
    return M_PI * radius * radius;
}

double Square::area() const {
    return side * side;
}

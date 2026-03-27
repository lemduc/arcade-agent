#include <stdio.h>
#include "util.h"

struct Rectangle {
    struct Point origin;
    double width;
    double height;
};

double area(struct Rectangle *r) {
    return r->width * r->height;
}

int main(int argc, char *argv[]) {
    struct Rectangle r = {{0, 0}, 10, 20};
    printf("Area: %f\n", area(&r));
    return 0;
}

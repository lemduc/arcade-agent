#pragma once

class Shape {
public:
    virtual double area() const = 0;
    virtual ~Shape() = default;
};

class Circle : public Shape {
public:
    Circle(double r) : radius(r) {}
    double area() const override;
private:
    double radius;
};

class Square : public Shape {
public:
    Square(double s) : side(s) {}
    double area() const override;
private:
    double side;
};

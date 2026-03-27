package com.example.calc;

import com.example.util.MathHelper;

public class Calculator {
    private MathHelper helper;

    public Calculator() {
        this.helper = new MathHelper();
    }

    public int add(int a, int b) {
        return helper.add(a, b);
    }

    public int subtract(int a, int b) {
        return a - b;
    }
}

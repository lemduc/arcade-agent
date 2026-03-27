package com.example.calc;

import com.example.util.MathHelper;

public class AdvancedCalculator extends Calculator implements Serializable {
    private MathHelper helper;

    public double power(double base, double exp) {
        return Math.pow(base, exp);
    }
}

interface Serializable {
    // marker interface
}

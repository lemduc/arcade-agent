package com.example.calc

import com.example.util.MathHelper
import com.example.util.MathHelper as MH

interface Ops {
    fun add(a: Int, b: Int): Int
}

interface ExtendedOps : Ops {
    fun subtract(a: Int, b: Int): Int
}

open class Calculator : Ops {
    override fun add(a: Int, b: Int): Int = MathHelper.sum(a, b)

    fun multiply(a: Int, b: Int): Int = a * b

    companion object Factory {
        fun create(): Calculator = Calculator()
    }
}

class AdvancedCalculator : Calculator() {
    fun power(base: Int, exp: Int): Int = base
}

data class Point(val x: Int, val y: Int)

enum class Mode {
    FAST,
    SAFE,
}

sealed class Result {
    class Ok(val value: Int) : Result()

    class Err(val message: String) : Result()
}

fun topLevelHelper(): Int = 1

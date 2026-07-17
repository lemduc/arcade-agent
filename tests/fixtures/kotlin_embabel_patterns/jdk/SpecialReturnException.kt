package com.embabel.patterns.jdk

/**
 * Extending unresolved JDK types must not crash or invent fake extends edges.
 */
class SpecialReturnException(message: String) : RuntimeException(message)

class BadInput : IllegalArgumentException("bad")

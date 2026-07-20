package com.embabel.patterns.annotation

/**
 * Minimized from embabel LlmTool / annotations.kt patterns:
 * annotation class with nested annotations and default array values.
 */
@Target(AnnotationTarget.FUNCTION)
@Retention(AnnotationRetention.RUNTIME)
annotation class LlmTool(
    val description: String = "",
    val metadata: Array<Meta> = [],
) {
    annotation class Meta(val key: String, val value: String)

    @Target(AnnotationTarget.VALUE_PARAMETER)
    annotation class Param(val description: String)
}

@Target(AnnotationTarget.CLASS)
@Retention(AnnotationRetention.RUNTIME)
annotation class EmbabelComponent(val scan: Boolean = true)

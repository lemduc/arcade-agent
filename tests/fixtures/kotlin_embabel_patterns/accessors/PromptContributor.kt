package com.embabel.patterns.accessors

import com.fasterxml.jackson.annotation.JsonIgnore

/**
 * Minimized from embabel PromptContributor: interface property accessors
 * with @get: annotations (tree-sitter may mark has_error on some of these).
 */
interface PromptElement {
    @get:JsonIgnore
    val role: String?
        get() = javaClass.simpleName
}

interface PromptContributor : PromptElement {
    fun contribution(): String
}

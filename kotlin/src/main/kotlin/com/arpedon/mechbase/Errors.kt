package com.arpedon.mechbase

import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Base class for all SDK errors. */
open class MechbaseException(
    message: String,
    val status: Int? = null,
    val body: String? = null,
) : Exception(message) {
    /** The server's `detail` message alone, without the status prefix [message] carries, to show the user. */
    val detail: String
        get() = message.orEmpty().let { m -> status?.let { m.removePrefix("$it ") } ?: m }
}

/** 401 / 403. */
class AuthException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 404. */
class NotFoundException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 422. */
class ValidationException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 409. */
class ConflictException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body) {
    /**
     * On a refused route start, the uuid of the execution already running on that
     * route — join it instead. Null for any other 409 (Swift `runningExecutionUuid`).
     */
    val runningExecutionUuid: String?
        get() = body?.let {
            runCatching { SDK_JSON.parseToJsonElement(it).jsonObject["running_execution_uuid"]?.jsonPrimitive?.contentOrNull }
                .getOrNull()
        }
}

/** 413. */
class PayloadTooLargeException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 5xx and other unexpected statuses. */
class ServerException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

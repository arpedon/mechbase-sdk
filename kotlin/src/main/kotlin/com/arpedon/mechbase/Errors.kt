package com.arpedon.mechbase

/** Base class for all SDK errors. */
open class MechbaseException(
    message: String,
    val status: Int? = null,
    val body: String? = null,
) : Exception(message)

/** 401 / 403. */
class AuthException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 404. */
class NotFoundException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 422. */
class ValidationException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 5xx and other unexpected statuses. */
class ServerException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

import com.vanniktech.maven.publish.JavadocJar
import com.vanniktech.maven.publish.KotlinJvm

plugins {
    kotlin("jvm") version "1.9.24"
    kotlin("plugin.serialization") version "1.9.24"
    id("com.vanniktech.maven.publish") version "0.33.0"
}

group = "com.arpedon"
version = "0.2.1"

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlin:kotlin-stdlib")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
}

kotlin {
    jvmToolchain(11)
}

// Examples live in ./examples but are NOT part of the main artifact.
// Compile them on demand with: ./gradlew compileExamples
sourceSets {
    create("examples") {
        kotlin.srcDir("examples")
        compileClasspath += sourceSets["main"].output + configurations["compileClasspath"]
        runtimeClasspath += output + compileClasspath
    }
}

tasks.register("compileExamples") {
    dependsOn("compileExamplesKotlin")
}

tasks.test {
    useJUnit()
    testLogging {
        events("passed", "failed", "skipped")
        showStandardStreams = true
    }
}

mavenPublishing {
    // Uploads to the Sonatype Central Portal (central.sonatype.com) and releases.
    // Credentials + signing come from env in CI (see .github/workflows/publish-kotlin.yml).
    publishToMavenCentral()
    signAllPublications()

    coordinates(group.toString(), "mechbase-sdk", version.toString())

    // Empty javadoc jar satisfies Central's requirement without pulling in Dokka.
    // ponytail: swap JavadocJar.Empty() -> JavadocJar.Dokka(...) if real API docs are wanted.
    configure(KotlinJvm(javadocJar = JavadocJar.Empty(), sourcesJar = true))

    pom {
        name.set("mechbase-sdk")
        description.set("Official Kotlin/JVM client for the Mechbase condition-monitoring API")
        inceptionYear.set("2026")
        url.set("https://github.com/arpedon/mechbase-sdk")
        licenses {
            license {
                name.set("MIT License")
                url.set("https://opensource.org/licenses/MIT")
            }
        }
        developers {
            developer {
                id.set("arpedon")
                name.set("Arpedon")
                url.set("https://github.com/arpedon")
            }
        }
        scm {
            url.set("https://github.com/arpedon/mechbase-sdk")
            connection.set("scm:git:git://github.com/arpedon/mechbase-sdk.git")
            developerConnection.set("scm:git:ssh://git@github.com/arpedon/mechbase-sdk.git")
        }
    }
}

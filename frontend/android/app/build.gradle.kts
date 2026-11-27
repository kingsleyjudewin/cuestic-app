import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// ---------------------------------------------------------------------------
// Release signing.
// Values come from android/key.properties (local, git-ignored) or environment variables (CI):
//   storeFile     / ANDROID_KEYSTORE_PATH      path to the .jks upload keystore
//   storePassword / ANDROID_KEYSTORE_PASSWORD
//   keyAlias      / ANDROID_KEY_ALIAS
//   keyPassword   / ANDROID_KEY_PASSWORD
// A release build without them FAILS; it is never silently signed with the debug key.
// ---------------------------------------------------------------------------
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    FileInputStream(keystorePropertiesFile).use { keystoreProperties.load(it) }
}

fun signingValue(propertyKey: String, envKey: String): String? =
    (keystoreProperties.getProperty(propertyKey) ?: System.getenv(envKey))?.takeIf { it.isNotBlank() }

val releaseStoreFile = signingValue("storeFile", "ANDROID_KEYSTORE_PATH")
val releaseStorePassword = signingValue("storePassword", "ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingValue("keyAlias", "ANDROID_KEY_ALIAS")
val releaseKeyPassword = signingValue("keyPassword", "ANDROID_KEY_PASSWORD")
val missingReleaseSigning = listOfNotNull(
    if (releaseStoreFile == null) "storeFile/ANDROID_KEYSTORE_PATH" else null,
    if (releaseStorePassword == null) "storePassword/ANDROID_KEYSTORE_PASSWORD" else null,
    if (releaseKeyAlias == null) "keyAlias/ANDROID_KEY_ALIAS" else null,
    if (releaseKeyPassword == null) "keyPassword/ANDROID_KEY_PASSWORD" else null,
)

android {
    namespace = "edu.university.club.mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "edu.university.club.mobile"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // From pubspec.yaml `version:` or --build-name / --build-number.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (missingReleaseSigning.isEmpty()) {
                storeFile = file(releaseStoreFile!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

// Stop release packaging with a clear message when signing is not configured.
tasks.matching { it.name.startsWith("package") && it.name.endsWith("Release") }.configureEach {
    doFirst {
        if (missingReleaseSigning.isNotEmpty()) {
            throw GradleException(
                "Release signing is not configured (missing: ${missingReleaseSigning.joinToString()}). " +
                    "Create android/key.properties or set the ANDROID_KEYSTORE_* / ANDROID_KEY_* " +
                    "environment variables. See DEPLOYMENT.md > Android signing."
            )
        }
        val store = file(releaseStoreFile!!)
        if (!store.exists()) {
            throw GradleException("Release keystore not found at: ${store.path}")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

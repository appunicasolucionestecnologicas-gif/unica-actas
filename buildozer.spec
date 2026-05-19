[app]
title = UNICA Libro de Actas
package.name = unicaactas
package.domain = com.pombar.unica
source.dir = .
source.include_exts = py,json,db
version = 1.0
requirements = python3,kivy==2.3.0
orientation = portrait
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 0

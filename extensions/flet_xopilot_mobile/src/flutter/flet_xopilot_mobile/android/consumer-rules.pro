# LiteRT-LM JNI looks up Kotlin configuration getters by their original names.
# R8 cannot see these native calls; renaming/removing getEnableThinking() causes
# a fatal JNI error when creating the first Live conversation in a release APK.
-keep class com.google.ai.edge.litertlm.** { *; }

/** Shared model-visibility state used by hydration and global settings. */
export const studioModelRuntime = {
  initializedMatureModels: new Set<string>(),
  visibilityHydrated: false,
  defaultsVersion: 1,
}

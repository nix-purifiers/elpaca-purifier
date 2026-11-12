{ lib }:
{
  src,
  lockFile ? src + "/elpaca-purifier.lock.json",
  nativeLockFile ? src + "/elpaca-lock.el",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  recipes = data.recipes or [ ];
  component =
    s:
    builtins.isString s
    && builtins.match "[A-Za-z0-9_.+-]+" s != null
    && !(builtins.elem s [
      "."
      ".."
    ]);
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "elpaca"
    && builtins.isString (data.sdk or null)
    && builtins.isString (data.native or null)
    && builtins.isList recipes
    && builtins.isList entries
    && builtins.all (
      recipe:
      builtins.isAttrs recipe
      && component (recipe.name or null)
      && component (recipe.repo or null)
      && component (recipe.build or null)
      && builtins.isString (recipe.recipe or null)
    ) recipes
    && builtins.all (
      entry:
      builtins.isAttrs entry
      && component (entry.path or null)
      && builtins.isString (entry.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
      && builtins.isAttrs (entry.git or null)
      && builtins.isString (entry.git.url or null)
      && lib.hasPrefix "https://" entry.git.url
      && builtins.isString (entry.git.rev or null)
      && builtins.match "[0-9a-f]{40}" entry.git.rev != null
      && (entry.git.submodules or null) == false
      && (entry.git.leaveDotGit or null) == true
      && builtins.isAttrs (entry.git.commitObject or null)
      && builtins.isString (entry.git.commitObject.object or null)
      && (entry.git.commitObject.gitlinks or null) == [ ]
    ) entries;
  valid =
    shape
    && builtins.pathExists nativeLockFile
    && data.native == builtins.readFile nativeLockFile
    && builtins.length recipes == builtins.length entries
    && builtins.length (lib.unique (map (r: r.name) recipes)) == builtins.length recipes
    && builtins.length (lib.unique (map (r: r.build) recipes)) == builtins.length recipes
    && builtins.length (lib.unique (map (r: r.repo) recipes)) == builtins.length recipes
    &&
      builtins.sort builtins.lessThan (map (r: r.repo) recipes)
      == builtins.sort builtins.lessThan (map (e: e.path) entries);
in
{
  purifier = "elpaca";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Elpaca lock is missing, malformed, or stale; run elpaca-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}

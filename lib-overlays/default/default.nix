final: prev: {
  elpaca-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}

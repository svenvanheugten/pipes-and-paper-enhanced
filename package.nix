{ lib, stdenvNoCC, makeWrapper, python3, openssh }:

let
  pythonEnv = python3.withPackages (ps: [ ps.websockets ]);
in
stdenvNoCC.mkDerivation {
  pname = "pipes-and-paper-enhanced";
  version = "0-unstable";

  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./main.py
      ./index.html
      ./src
      ./static
    ];
  };

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/pipes-and-paper-enhanced
    cp -r main.py index.html src static $out/share/pipes-and-paper-enhanced/

    # main.py resolves index.html and static/ relative to its own location.
    makeWrapper ${pythonEnv}/bin/python3 $out/bin/pipes-and-paper-enhanced \
      --add-flags $out/share/pipes-and-paper-enhanced/main.py \
      --prefix PATH : ${lib.makeBinPath [ openssh ]}

    runHook postInstall
  '';

  meta = {
    description = "Screen share in the browser for ReMarkable tablets";
    homepage = "https://github.com/Pyrrhu5/pipes-and-paper-enhanced";
    license = lib.licenses.mit;
    mainProgram = "pipes-and-paper-enhanced";
    platforms = lib.platforms.unix;
  };
}

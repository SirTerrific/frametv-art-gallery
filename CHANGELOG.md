# Changelog

## [2.0.0](https://github.com/mrtncode/frametv-art-gallery/compare/v1.5.0...v2.0.0) (2026-08-28)


### ⚠ BREAKING CHANGES

* Design UI refactor ([#98](https://github.com/mrtncode/frametv-art-gallery/issues/98))

### Features

* Add Desktop Client 🥳 ([#105](https://github.com/mrtncode/frametv-art-gallery/issues/105)) ([4638b21](https://github.com/mrtncode/frametv-art-gallery/commit/4638b21be43ecd376dde343b197bfbdf7d8dc460))
* Design refactoring/ rebranding ([2c5b778](https://github.com/mrtncode/frametv-art-gallery/commit/2c5b778f94d608f5beaaef51024dc28f1b96a2fe))
* Design UI refactor ([#98](https://github.com/mrtncode/frametv-art-gallery/issues/98)) ([ea96d37](https://github.com/mrtncode/frametv-art-gallery/commit/ea96d373bdfd9a17330555f36e98ba558932d1bb))


### Bug Fixes

* Cut a call that never comes back, without waiting out the deadline ([#92](https://github.com/mrtncode/frametv-art-gallery/issues/92)) ([ed77fb9](https://github.com/mrtncode/frametv-art-gallery/commit/ed77fb97dde497d4023f1b377315be224c995093))
* keep the token a Frame TV hands back, so it stops asking to pair again ([#94](https://github.com/mrtncode/frametv-art-gallery/issues/94)) ([7f2f88f](https://github.com/mrtncode/frametv-art-gallery/commit/7f2f88fc6c12a75d1cc8b63984d72492ef583420))
* Loading TV thumbnails ([#103](https://github.com/mrtncode/frametv-art-gallery/issues/103)) ([512736e](https://github.com/mrtncode/frametv-art-gallery/commit/512736ee14aa16eb720d9eefc4dd6371d3ea4a9a))
* reach a connection that is still being established, so an abandoned call lets the TV go ([#91](https://github.com/mrtncode/frametv-art-gallery/issues/91)) ([f1a753c](https://github.com/mrtncode/frametv-art-gallery/commit/f1a753c1a43081c57c37641666b3b99cec2e9737))
* release changelog formatting ([9270af5](https://github.com/mrtncode/frametv-art-gallery/commit/9270af5086653430018278a148a9ffaa04fb4a5d))
* release changelog messages ([0fd6509](https://github.com/mrtncode/frametv-art-gallery/commit/0fd6509fb95be5cf71fa49a6eed8773ce21a85d0))
* walk a gallery of thumbnails in batches, and learn from one visit to the next ([#93](https://github.com/mrtncode/frametv-art-gallery/issues/93)) ([217483e](https://github.com/mrtncode/frametv-art-gallery/commit/217483e16d51ea50b298c972f7cacec6f8c0de83))

## [1.5.0](https://github.com/mrtncode/frametv-art-gallery/compare/v1.4.1...v1.5.0) (2026-08-22)

If you find frametv-art-gallery helpful, I would be happy about stars ⭐️ and contributions :)

### Features

* Add 1-slot TV image mode ([#89](https://github.com/mrtncode/frametv-art-gallery/issues/89)) ([301d5cc](https://github.com/mrtncode/frametv-art-gallery/commit/301d5cce6b9b2d49ecdfc4a7d7e546ba92b2dc94))
* Choose the matte style and color when sending art to a TV ([#87](https://github.com/mrtncode/frametv-art-gallery/issues/87)) ([d7c03d3](https://github.com/mrtncode/frametv-art-gallery/commit/d7c03d3fe1d0d6d13970f57c6e6abc79a9f79adb))


### Bug Fixes

* Dependencies for immich ([fd3e63f](https://github.com/mrtncode/frametv-art-gallery/commit/fd3e63f31917fcdae24f6344d209fe1e39c15f44))
* Improve tv gallery stability ([409eed1](https://github.com/mrtncode/frametv-art-gallery/commit/409eed1b072195a858c53e967930b8a9022fb8c3))

## [1.4.1](https://github.com/mrtncode/frametv-art-gallery/compare/v1.4.0...v1.4.1) (2026-08-14)


### Bug Fixes

* Let the user set the "PORT" env variable to adjust the port in the host mode (required for auto disovery in v1.4.0) ([3f57567](https://github.com/mrtncode/frametv-art-gallery/commit/3f5756773b16be223dcf9b0399fd74914d499a95))

## [1.4.0](https://github.com/mrtncode/frametv-art-gallery/compare/v1.3.0...v1.4.0) (2026-08-14)


### Features

* Add TV auto discovery ([#83](https://github.com/mrtncode/frametv-art-gallery/issues/83)) ([36efdee](https://github.com/mrtncode/frametv-art-gallery/commit/36efdee6a452dfad3a4928b74e06ffb3ce11ab15))

  To use the auto discovery feature, make sure you are using network="host" in docker :)
* Delete several images from a TV at once ([#75](https://github.com/mrtncode/frametv-art-gallery/issues/75)) ([110aed1](https://github.com/mrtncode/frametv-art-gallery/commit/110aed13347856794eff6b082fcaba653df3ea67))
* Download a backup of the gallery ([#81](https://github.com/mrtncode/frametv-art-gallery/issues/81)) ([0adceaf](https://github.com/mrtncode/frametv-art-gallery/commit/0adceaf5498bdb66fb6f86f46be8fdef1917d851))
* offer the Frame TV panel size as a crop preset (4K) ([#82](https://github.com/mrtncode/frametv-art-gallery/issues/82)) ([01017a4](https://github.com/mrtncode/frametv-art-gallery/commit/01017a460e797b0a3ce779d5d2a4be6ee4d54df8))
* rotate through an album on a TV at a chosen interval ([#72](https://github.com/mrtncode/frametv-art-gallery/issues/72)) ([7879b0d](https://github.com/mrtncode/frametv-art-gallery/commit/7879b0dde168ea1c22660fded0d7dc1b04a20396))
* Search the gallery and choose its order ([#79](https://github.com/mrtncode/frametv-art-gallery/issues/79)) ([d437fad](https://github.com/mrtncode/frametv-art-gallery/commit/d437fad2db266f54ff4470c598d7985ec0bb0099))
* serve downscaled copies to the gallery grid ([#77](https://github.com/mrtncode/frametv-art-gallery/issues/77)) ([f1f9aa6](https://github.com/mrtncode/frametv-art-gallery/commit/f1f9aa602daec2d21c66c25858f65b695c2bcd1b))
* Tell the user when an artwork is already in the gallery and provide a „Check library“ functionality ([#80](https://github.com/mrtncode/frametv-art-gallery/issues/80)) ([9d8ac64](https://github.com/mrtncode/frametv-art-gallery/commit/9d8ac648971d6598ad2cffbf3731e433f1e8e9fe))


### Bug Fixes

* Let a deliberate action wait its turn when the TV is busy ([#73](https://github.com/mrtncode/frametv-art-gallery/issues/73)) ([21f8e75](https://github.com/mrtncode/frametv-art-gallery/commit/21f8e7543a1e9795c8694056a620598b55e56745))
* show the real name and date of the images on a TV ([#74](https://github.com/mrtncode/frametv-art-gallery/issues/74)) ([3db6ce6](https://github.com/mrtncode/frametv-art-gallery/commit/3db6ce6b5b90c346e4e17fd08e1667d3023dc01c))

## [1.3.0](https://github.com/mrtncode/frametv-art-gallery/compare/v1.2.0...v1.3.0) (2026-08-11)


### Features

* Album selection, bulk actions ([#59](https://github.com/mrtncode/frametv-art-gallery/issues/59)) and a dark mode ([#63](https://github.com/mrtncode/frametv-art-gallery/issues/63)) ([e51dd36](https://github.com/mrtncode/frametv-art-gallery/commit/e51dd36a2aa5a6e0441c43cdb5a4c6c9a89dca41))


### Bug Fixes

* Keep one unresponsive TV from freezing the app ([#62](https://github.com/mrtncode/frametv-art-gallery/issues/62)) ([0bbc6f9](https://github.com/mrtncode/frametv-art-gallery/commit/0bbc6f93c7e9a7fc08c7c9e84efd4da02242d148))
* stamp a newly created database so migrations do not replay over it ([#64](https://github.com/mrtncode/frametv-art-gallery/issues/64)) ([45c3545](https://github.com/mrtncode/frametv-art-gallery/commit/45c3545ff63bf9be2253da35effa14bcace264e6))

## [1.2.0](https://github.com/mrtncode/frametv-art-gallery/compare/v1.1.5...v1.2.0) (2026-06-13)


### Features

* Add caching for TV images (speedup loading) ([22206e8](https://github.com/mrtncode/frametv-art-gallery/commit/22206e80b40e564b2a23bdb866c70fe5b886a03e))


### Bug Fixes

* fetch TV images with one batch request from the TV ([2d1a59b](https://github.com/mrtncode/frametv-art-gallery/commit/2d1a59bbf28c8532e4bfc58f1056fd099c885080))
* reduce backend requests ([5897fc7](https://github.com/mrtncode/frametv-art-gallery/commit/5897fc7b34eed5a30185f173cdfba0d5bc3bfc67))

## [1.1.5](https://github.com/mrtncode/frametv-art-gallery/compare/v1.1.4...v1.1.5) (2026-06-03)


### Bug Fixes

* build errors ([223a855](https://github.com/mrtncode/frametv-art-gallery/commit/223a855a212db5d087c415a74090e660666a9964))

## [1.1.4](https://github.com/mrtncode/frametv-art-gallery/compare/v1.1.3...v1.1.4) (2026-05-24)


### Bug Fixes

* adjust page headlines ([62e3b6d](https://github.com/mrtncode/frametv-art-gallery/commit/62e3b6da8c8ce8697ddc3785f997e5eb7c871c1f))
* fix text templates ([fd4fe25](https://github.com/mrtncode/frametv-art-gallery/commit/fd4fe256539538fabb401cd2dc4076c322823ee8))

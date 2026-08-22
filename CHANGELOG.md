# Changelog

## [1.6.2](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.6.1...v1.6.2) (2026-08-22)


### Bug Fixes

* say why the app will not start after going back to an older image ([78bfd3c](https://github.com/SirTerrific/frametv-art-gallery/commit/78bfd3ceffc5513b3fb9be48287339efa1aa70bc))

## [1.6.1](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.6.0...v1.6.1) (2026-08-22)


### Bug Fixes

* only send a matte when one was actually chosen ([76a4db0](https://github.com/SirTerrific/frametv-art-gallery/commit/76a4db0a5f6d7f0a129be3889e0821308047036f))

## [1.6.0](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.7...v1.6.0) (2026-08-22)


### Features

* choose the matte style and color when sending art to a TV ([df31bc5](https://github.com/SirTerrific/frametv-art-gallery/commit/df31bc5c58ae7b14c9ab9e5c47dbb7eff3d3b850))

## [1.5.7](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.6...v1.5.7) (2026-08-11)


### Bug Fixes

* retry a refused thumbnail batch one image at a time ([ae4a20d](https://github.com/SirTerrific/frametv-art-gallery/commit/ae4a20d41e11e686bb2411a2dad21c6d57dd56a3))

## [1.5.6](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.5...v1.5.6) (2026-08-11)


### Bug Fixes

* stop asking a TV for a preview it has already said it does not have ([f793a67](https://github.com/SirTerrific/frametv-art-gallery/commit/f793a6772214d68ef31595f483cd85599a2c86a5))

## [1.5.5](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.4...v1.5.5) (2026-08-11)


### Bug Fixes

* show a thumbnail for the art the batch endpoint skips ([929bda6](https://github.com/SirTerrific/frametv-art-gallery/commit/929bda6113c53a61f8f514cce39772c105c065d4))

## [1.5.4](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.3...v1.5.4) (2026-08-11)


### Bug Fixes

* file a TV thumbnail under the content id the gallery looks up ([b94785a](https://github.com/SirTerrific/frametv-art-gallery/commit/b94785a855bcfe846f9445578782898f49034d5f))

## [1.5.3](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.2...v1.5.3) (2026-08-11)


### Bug Fixes

* fetch TV thumbnails in batches so a gallery stops coming back blank ([b94b8c9](https://github.com/SirTerrific/frametv-art-gallery/commit/b94b8c9de1d221b085540f7863afeb28a70280bc))

## [1.5.2](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.1...v1.5.2) (2026-08-11)


### Bug Fixes

* let a deliberate action wait its turn when the TV is busy ([17a51ec](https://github.com/SirTerrific/frametv-art-gallery/commit/17a51ec46dd439fbc57fd0938cb17d1429c58d72))

Also picks up the upstream dependency updates merged from mrtncode/frametv-art-gallery.
The two fixes upstream squashed into its own history (#62, #64) already shipped here in
v1.5.0 and v1.5.1, so they are not repeated.

## [1.5.1](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.5.0...v1.5.1) (2026-08-11)


### Bug Fixes

* forget images the TV no longer holds ([f267b48](https://github.com/SirTerrific/frametv-art-gallery/commit/f267b48312caa1d8d81e8babe447df72375ed249))

## [1.5.0](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.4.0...v1.5.0) (2026-08-11)


### Features

* sample the TV content list, and offer a 4K crop preset ([4b89728](https://github.com/SirTerrific/frametv-art-gallery/commit/4b89728b68983872400c5fcd644e2b975d21ca4a))
* select several images on a TV and delete them in one go ([a18bf0d](https://github.com/SirTerrific/frametv-art-gallery/commit/a18bf0d41e47e553d313171b91053b4a4135c634))


### Bug Fixes

* never let the slideshow pull a TV into art mode ([0f7600d](https://github.com/SirTerrific/frametv-art-gallery/commit/0f7600d5ac099e4d1d46395b6f8790cbfac40b72))
* show the real name and date of the images on a TV ([03f696c](https://github.com/SirTerrific/frametv-art-gallery/commit/03f696c102c86f81fbc216bd12b032c23efaa0b8))

## [1.4.0](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.3.0...v1.4.0) (2026-08-10)


### Features

* thumbnails, wake-on-lan, slideshow, search, duplicates and backup ([f2f23dc](https://github.com/SirTerrific/frametv-art-gallery/commit/f2f23dca02218616de2261ce350f3bda1e1abd5f))


### Bug Fixes

* stamp a newly created database so migrations do not replay over it ([7d4e952](https://github.com/SirTerrific/frametv-art-gallery/commit/7d4e952b42a806c9044f567b63ee8a9e16f52542))

## [1.3.0](https://github.com/SirTerrific/frametv-art-gallery/compare/v1.2.0...v1.3.0) (2026-08-10)


### Features

* add a light and dark mode toggle ([fccad0d](https://github.com/SirTerrific/frametv-art-gallery/commit/fccad0d9d216966ef5ef129ef7b488cf8c7c0d12))
* Add caching for TV images (speedup loading) ([22206e8](https://github.com/SirTerrific/frametv-art-gallery/commit/22206e80b40e564b2a23bdb866c70fe5b886a03e))
* Add toast message to indicate upload status ([d18a8f0](https://github.com/SirTerrific/frametv-art-gallery/commit/d18a8f0e29cd74ce5317efb7eb6f653e19cba511))
* delete selected images, and choose the album when dropping files ([ef5480c](https://github.com/SirTerrific/frametv-art-gallery/commit/ef5480c72388272d50d742a05600eb22cc7d3661))
* Management of images on the TV ([def3e80](https://github.com/SirTerrific/frametv-art-gallery/commit/def3e80c612eee2f4270afadbc8fdcf56b88140d))
* pick an album when uploading, and move images in bulk ([b3d4045](https://github.com/SirTerrific/frametv-art-gallery/commit/b3d4045c25c539c04e70de2c108c3bdb1ebcba5a))
* send a whole album to a TV ([e8e87cb](https://github.com/SirTerrific/frametv-art-gallery/commit/e8e87cb4d66587b0effce24d2313cb6fb635c10a))


### Bug Fixes

* adjust page headlines ([62e3b6d](https://github.com/SirTerrific/frametv-art-gallery/commit/62e3b6da8c8ce8697ddc3785f997e5eb7c871c1f))
* build errors ([223a855](https://github.com/SirTerrific/frametv-art-gallery/commit/223a855a212db5d087c415a74090e660666a9964))
* fetch TV images with one batch request from the TV ([2d1a59b](https://github.com/SirTerrific/frametv-art-gallery/commit/2d1a59bbf28c8532e4bfc58f1056fd099c885080))
* fix text templates ([fd4fe25](https://github.com/SirTerrific/frametv-art-gallery/commit/fd4fe256539538fabb401cd2dc4076c322823ee8))
* make every label readable in dark mode ([c242c3f](https://github.com/SirTerrific/frametv-art-gallery/commit/c242c3f54c1ba93911f9fbe38b3e8621b9d65cb7))
* reduce backend requests ([5897fc7](https://github.com/SirTerrific/frametv-art-gallery/commit/5897fc7b34eed5a30185f173cdfba0d5bc3bfc67))
* remove security header that caused problems (infinite loading) ([bcbd347](https://github.com/SirTerrific/frametv-art-gallery/commit/bcbd347ebc0be08b3a07202bbc5c36250cb3c5d9))
* stop an unresponsive TV from taking the whole app down ([8bec083](https://github.com/SirTerrific/frametv-art-gallery/commit/8bec083f8d929ec8f8175b946ff22ff767fea690))
* stop the circuit breaker from shouting, and from blocking deliberate actions ([76e9466](https://github.com/SirTerrific/frametv-art-gallery/commit/76e946641cd782babd46618000e9407519fc2ef6))
* talk to a TV one connection at a time ([4ba7e93](https://github.com/SirTerrific/frametv-art-gallery/commit/4ba7e9341073a5e656d42e1d3f3c5fae63de6dc9))

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

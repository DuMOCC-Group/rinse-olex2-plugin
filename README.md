# RINSE for Olex2

An Olex2 plugin for calculating and displaying the RINSE hash of the currently
displayed crystallographic model.

## Requirements

- Olex2 with Python 3.8 or newer
- An internet connection the first time the plugin needs `rinse-descriptor`,
  unless you install it in Olex2's Python runtime beforehand

## Install the plugin

1. Close Olex2.
2. Copy the complete `plugin-RINSE` folder from this repository into:

   ```text
   <Olex2 installation folder>\util\pyUtil\PluginLib
   ```

   For example, if Olex2 is installed in `D:\Apps\Olex2`, copy it to
   `D:\Apps\Olex2\util\pyUtil\PluginLib\plugin-RINSE`. Make sure the plugin
   files are directly inside that folder (not inside an extra nested
   `plugin-RINSE` folder).
3. Register the plugin in `<Olex2 BaseDir>\plugins.xld`. Add `<RINSE>` as an
   entry inside the existing `<Plugin ... >` section, preserving any other
   entries. For example:

   ```text
   <Plugin
     <RINSE>
   >
   ```

   If there is no `<Plugin` section yet, create the section as shown. Olex2's
   `BaseDir` is its installation folder.
   If there is no `plugins.xld` file, create it and add the above text.
4. Start Olex2 and open a model. If `rinse-descriptor` is not already
   available, the plugin will try to install it in Olex2's Python environment
   the first time it loads. If needed, install it manually from Olex2's main
   console:

   ```text
   spy.pip('rinse-descriptor')
   ```

   Restart Olex2 after a manual install.
5. Check the runtime from Olex2's main console:

   ```text
   spy.RINSE.check_environment()
   ```

   This prints Olex2's Python version and whether `rinse-descriptor` and
   `cctbx-base` are installed in that runtime.

The plugin calculates the descriptor and hash automatically when a model is
loaded or refined. It stores them in the active CIF metadata as
`_rinse_descriptor` (a JSON array of descriptor values) and `_rinse_hash`.
Olex2 includes these data items when the CIF is saved. To calculate them
manually, run `spy.RINSE.calculate()` in Olex2's main console. The hash is
printed in the console and displayed in the RINSE plugin panel; the descriptor
is stored in the CIF metadata.

## Development status

This integration uses Olex2's `FullMatrixRefine().xray_structure()` interface
to obtain the current cctbx structure, calculates its descriptor with
`rinse_descriptor.descriptor`, then converts it to the RINSE locality-sensitive
hash with `rinse_descriptor.descriptor_hash`. The environment check reports
versions; successfully running `spy.RINSE.calculate()` confirms that the
installed package and Olex2's current model work together.

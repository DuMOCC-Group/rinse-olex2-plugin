"""Olex2 entry point for calculating the RINSE hash."""

import json
import importlib.metadata
import importlib
import os
import sys

import olx
from olexFunctions import OlexFunctions

OV = OlexFunctions()

try:
  from_outside = False
  p_path = os.path.dirname(os.path.abspath(__file__))
except NameError:
  from_outside = True
  p_path = os.path.dirname(os.path.abspath("__file__"))

with open(os.path.join(p_path, 'def.txt')) as plugin_definition:
  d = {}
  for line in plugin_definition:
    line = line.strip()
    if not line or line.startswith("#"):
      continue
    key, value = line.split("=", 1)
    d[key.strip()] = value.strip()

p_name = d['p_name']
p_htm = d['p_htm']
p_img = eval(d['p_img'])
p_scope = d['p_scope']

OV.SetVar('RINSE_plugin_path', p_path)
OV.SetVar('RINSE_hash', 'Waiting for a structure')
OV.SetVar('RINSE_status', 'Load a structure to calculate its RINSE hash')

from PluginTools import PluginTools as PT


class RINSE(PT):

  def __init__(self):
    super(RINSE, self).__init__()
    self.p_name = p_name
    self.p_path = p_path
    self.p_scope = p_scope
    self.p_htm = p_htm
    self.p_img = p_img
    self.deal_with_phil(operation='read')
    self.print_version_date()
    if not from_outside:
      self.setup_gui()
    self._dependency_install_attempted = False
    OV.registerFunction(self.check_environment, True, "RINSE")
    OV.registerFunction(self.calculate, True, "RINSE")
    self._register_calculation_hooks()
    try:
      self._get_rinse_functions()
      OV.SetVar('RINSE_status', 'Ready; waiting for a structure')
    except Exception as error:
      self._show_calculation_error(error)
    if olx.IsFileLoaded() == 'true':
      self._calculate_automatically()

  def _register_calculation_hooks(self):
    """Recalculate when reflections change or a refinement run completes."""
    file_change_listeners = olx.FileChangeListeners
    file_change_listeners[:] = [
      listener for listener in file_change_listeners
      if getattr(listener, '__name__', None) != "rinse_on_file_change"
    ]
    file_change_listeners.append(self.rinse_on_file_change)

    from RunPrg import LM
    LM.onEnd_listeners[:] = [
      listener for listener in LM.onEnd_listeners
      if getattr(listener, '__name__', None) != "rinse_on_refinement_end"
    ]
    LM.register_listener(self.rinse_on_refinement_end, "onEnd")

  def rinse_on_file_change(self, filetype):
    if filetype in ("structure", "hkl"):
      self._calculate_automatically()

  def rinse_on_refinement_end(self, run):
    if getattr(run, "prgType", None) == "refinement":
      self._calculate_automatically()

  def _calculate_automatically(self):
    try:
      self.calculate()
    except Exception as error:
      self._show_calculation_error(error)

  def _show_calculation_error(self, error):
    message = "RINSE calculation failed: %s" % error
    print(message)
    OV.SetVar('RINSE_hash', 'Unavailable')
    OV.SetVar('RINSE_status', message)
    OV.UpdateHtml()

  def _get_rinse_functions(self):
    try:
      rinse_descriptor = importlib.import_module('rinse_descriptor')
    except ModuleNotFoundError as error:
      if error.name != 'rinse_descriptor':
        raise
      if self._dependency_install_attempted:
        raise RuntimeError(
          "rinse-descriptor is still unavailable after the automatic install "
          "attempt; see the Olex2 console for pip output"
        ) from error

      self._dependency_install_attempted = True
      message = "Installing rinse-descriptor in the Olex2 Python environment..."
      print(message)
      OV.SetVar('RINSE_hash', 'Installing...')
      OV.SetVar('RINSE_status', message)
      OV.UpdateHtml()

      import olexex
      olexex.pip('rinse-descriptor')
      importlib.invalidate_caches()
      try:
        rinse_descriptor = importlib.import_module('rinse_descriptor')
      except ModuleNotFoundError as install_error:
        if install_error.name != 'rinse_descriptor':
          raise
        raise RuntimeError(
          "Automatic installation of rinse-descriptor failed; see the "
          "Olex2 console for pip output"
        ) from install_error

    return rinse_descriptor.descriptor, rinse_descriptor.descriptor_hash

  def check_environment(self):
    """Print the Python and RINSE dependency versions used by Olex2."""
    lines = [f"Olex2 Python: {sys.version.split()[0]}"]
    for package in ("rinse-descriptor", "cctbx-base"):
      try:
        version = importlib.metadata.version(package)
      except importlib.metadata.PackageNotFoundError:
        version = "not installed"
      lines.append(f"{package}: {version}")

    report = "\n".join(lines)
    print(report)
    return report

  def calculate(self):
    """Calculate and display the RINSE descriptor and hash for the current model."""
    descriptor, descriptor_hash = self._get_rinse_functions()

    from refinement import FullMatrixRefine

    xray_structure = FullMatrixRefine().xray_structure()
    values = descriptor(xray_structure)
    rinse_hash = descriptor_hash(values)

    from CifInfo import CifTools

    cif_tools = CifTools()
    cif_tools.cif_block['_rinse_descriptor'] = json.dumps(
      values.tolist(),
      separators=(',', ':'),
      allow_nan=False,
    )
    cif_tools.cif_block['_rinse_hash'] = str(rinse_hash)

    OV.SetVar('RINSE_hash', rinse_hash)
    OV.SetVar(
      'RINSE_status',
      "Descriptor and hash will be included when the CIF is saved",
    )
    OV.UpdateHtml()
    print("RINSE hash: %s" % rinse_hash)
    return rinse_hash


RINSE_instance = RINSE()
print("OK.")

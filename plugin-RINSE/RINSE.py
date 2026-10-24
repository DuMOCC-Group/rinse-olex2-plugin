"""Olex2 entry point for calculating the RINSE hash."""

import importlib.metadata
import importlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import fields

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
    self._update_check_attempted = False
    self._rinse_update_notice = None
    OV.registerFunction(self.check_environment, True, "RINSE")
    OV.registerFunction(self.calculate, True, "RINSE")
    self._register_calculation_hooks()
    try:
      self._get_rinse_module()
      OV.SetVar(
        'RINSE_status',
        self._rinse_update_notice or 'Ready; waiting for a structure',
      )
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

  def _get_rinse_module(self):
    self._check_for_rinse_update()
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

    return rinse_descriptor

  def _check_for_rinse_update(self):
    if self._update_check_attempted:
      return
    self._update_check_attempted = True

    try:
      installed_version = importlib.metadata.version('rinse-descriptor')
    except importlib.metadata.PackageNotFoundError:
      return

    try:
      with urllib.request.urlopen(
        'https://pypi.org/pypi/rinse-descriptor/json',
        timeout=5,
      ) as response:
        latest_version = json.load(response)['info']['version']

      from pip._vendor.packaging.version import Version

      if Version(latest_version) <= Version(installed_version):
        print(
          "rinse-descriptor is up to date (%s)" % installed_version
        )
        return
    except (
      ImportError,
      KeyError,
      OSError,
      TypeError,
      urllib.error.URLError,
      ValueError,
    ) as error:
      self._rinse_update_notice = (
        "Could not check for rinse-descriptor updates: %s" % error
      )
      print(self._rinse_update_notice)
      return

    message = (
      "Updating rinse-descriptor from %s to %s..."
      % (installed_version, latest_version)
    )
    print(message)
    OV.SetVar('RINSE_status', message)
    OV.UpdateHtml()

    try:
      self._install_rinse_version(latest_version)
    except (ImportError, OSError, RuntimeError, ValueError) as error:
      self._rinse_update_notice = (
        "Update to rinse-descriptor %s failed: %s"
        % (latest_version, error)
      )
      print(self._rinse_update_notice)
      return

    self._rinse_update_notice = (
      "Updated rinse-descriptor from %s to %s; restart Olex2 to use it"
      % (installed_version, latest_version)
    )
    print(self._rinse_update_notice)

  @staticmethod
  def _install_rinse_version(version):
    import numpy
    import PIL
    import scipy
    import locale
    from pip._internal import main as pipmain

    data_dir = OV.DataDir()
    constraints_path = os.path.join(data_dir, "pip_constraints.txt")
    with open(constraints_path, "w") as constraints_file:
      constraints_file.write(
        "scipy==%s\nnumpy==%s\npillow==%s"
        % (scipy.__version__, numpy.__version__, PIL.__version__)
      )

    python_suffix = ""
    if sys.version_info.major >= 3 and sys.version_info.minor > 8:
      python_suffix = "-%s%s" % (
        sys.version_info.major,
        sys.version_info.minor,
      )
    target = os.path.join(data_dir, "site-packages" + python_suffix)
    saved_locale = locale.getlocale(locale.LC_CTYPE)
    original_get_terminal_size = os.get_terminal_size
    original_stdout_isatty = sys.stdout.isatty
    try:
      os.get_terminal_size = lambda handle=None: (100, 100)
      sys.stdout.isatty = lambda: False
      result = pipmain([
        "install",
        "--upgrade",
        "--target=%s" % target,
        "rinse-descriptor==%s" % version,
        "-c",
        constraints_path,
        "--no-input",
        "--disable-pip-version-check",
        "--progress-bar",
        "off",
      ])
    finally:
      os.get_terminal_size = original_get_terminal_size
      sys.stdout.isatty = original_stdout_isatty
      locale.setlocale(locale.LC_CTYPE, saved_locale)
    if result != 0:
      raise RuntimeError("pip exited with status %s" % result)
    importlib.invalidate_caches()

  @staticmethod
  def _replace_cif_loop(cif_block, header, rows):
    from iotbx.cif import model

    for cif_loop in list(cif_block.loops.values()):
      if any(item in cif_loop for item in header):
        for item in list(cif_loop.keys()):
          del cif_block[item]

    for item in header:
      if item in cif_block:
        del cif_block[item]

    cif_loop = model.loop(header=header)
    for row in rows:
      cif_loop.add_row(row)
    cif_block.add_loop(cif_loop)

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
    rinse_descriptor = self._get_rinse_module()

    from refinement import FullMatrixRefine

    xray_structure = FullMatrixRefine().xray_structure()
    params = rinse_descriptor.RinseParams()
    values = rinse_descriptor.descriptor(xray_structure, params=params)
    hash_words = rinse_descriptor.DEFAULT_HASH_WORDS
    rinse_hash = rinse_descriptor.descriptor_hash(
      values,
      n_words=hash_words,
    )

    from CifInfo import CifTools

    cif_tools = CifTools()
    if '_rinse_descriptor' in cif_tools.cif_block:
      del cif_tools.cif_block['_rinse_descriptor']

    descriptor_values = values.reshape(-1)
    self._replace_cif_loop(
      cif_tools.cif_block,
      ('_rinse_elements.index', '_rinse_elements.value'),
      [
        (str(index), repr(float(value)))
        for index, value in enumerate(descriptor_values, start=1)
      ],
    )

    rinse_params = [
      (field.name, getattr(params, field.name))
      for field in fields(params)
    ]
    rinse_params.extend((
      ('descriptor_version', rinse_descriptor.__version__),
      ('hash_words', hash_words),
    ))
    self._replace_cif_loop(
      cif_tools.cif_block,
      ('_rinse_parameters.name', '_rinse_parameters.value'),
      [
        (name, json.dumps(value, allow_nan=False))
        for name, value in rinse_params
      ],
    )
    cif_tools.cif_block['_rinse_hash'] = str(rinse_hash)

    OV.SetVar('RINSE_hash', rinse_hash)
    OV.SetVar(
      'RINSE_status',
      "Descriptor, parameters, and hash will be included when the CIF is saved"
      + (
        " (%s)" % self._rinse_update_notice
        if self._rinse_update_notice
        else ""
      ),
    )
    OV.UpdateHtml()
    print("RINSE hash: %s" % rinse_hash)
    return rinse_hash


RINSE_instance = RINSE()
print("OK.")

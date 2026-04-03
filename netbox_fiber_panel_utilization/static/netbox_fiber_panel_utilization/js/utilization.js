// Fiber Patch Panel Utilization - Color threshold logic
// Applies CSS color classes to utilization bars based on configurable thresholds.
// Req 1.6, 5.5: green < warning_threshold <= yellow < critical_threshold <= red

document.addEventListener('DOMContentLoaded', function () {
  var bars = document.querySelectorAll('.utilization-bar');
  for (var i = 0; i < bars.length; i++) {
    var bar = bars[i];
    var utilization = parseFloat(bar.getAttribute('data-utilization'));
    var warning = parseFloat(bar.getAttribute('data-warning-threshold'));
    var critical = parseFloat(bar.getAttribute('data-critical-threshold'));

    if (isNaN(utilization) || isNaN(warning) || isNaN(critical)) {
      continue;
    }

    // Remove any existing color class before applying
    bar.classList.remove('utilization-green', 'utilization-yellow', 'utilization-red');

    if (utilization >= critical) {
      bar.classList.add('utilization-red');
    } else if (utilization >= warning) {
      bar.classList.add('utilization-yellow');
    } else {
      bar.classList.add('utilization-green');
    }
  }
});

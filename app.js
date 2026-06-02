document.addEventListener("DOMContentLoaded", () => {
  // Center map globally with a friendly starting view
  const map = L.map("map", {
    center: [25, 0],
    zoom: 3,
    minZoom: 2,
    maxBounds: [[-85, -180], [85, 180]],
    zoomControl: false // Disable top-left control to prevent overlap with floating HUD
  });

  // Reposition zoom controls to the bottom-left corner
  L.control.zoom({
    position: "bottomleft"
  }).addTo(map);

  // Use CartoDB Positron bright light tiles (perfect for white-sand sunny themes)
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(map);

  // Details/Header panel DOM selections
  const detailsPanel = document.getElementById("details-panel");
  const detailsContent = document.getElementById("details-content");
  const closePanelBtn = document.getElementById("close-panel-btn");
  const headerPanel = document.getElementById("header-panel");
  const menuToggleBtn = document.getElementById("menu-toggle-btn");

  // Keep details panel hidden on initial load
  detailsPanel.classList.add("hidden");

  // Close panel event handler
  closePanelBtn.addEventListener("click", () => {
    detailsPanel.classList.add("hidden");
  });

  // Main menu collapse/expand state management
  // 1. Check localStorage for user preference (wrapped in try-catch to prevent crash if disabled)
  // 2. If no preference exists, default to collapsed on mobile (<768px), expanded on desktop
  let isMenuCollapsed = false;
  try {
    const cachedMenuState = localStorage.getItem("did_menu_collapsed");
    if (cachedMenuState !== null) {
      isMenuCollapsed = cachedMenuState === "true";
    } else {
      isMenuCollapsed = window.innerWidth <= 768;
    }
  } catch (e) {
    isMenuCollapsed = window.innerWidth <= 768;
  }

  // Apply initial collapsed state
  if (isMenuCollapsed) {
    headerPanel.classList.add("collapsed");
    menuToggleBtn.setAttribute("aria-label", "Expand menu");
  } else {
    headerPanel.classList.remove("collapsed");
    menuToggleBtn.setAttribute("aria-label", "Minimize menu");
  }

  // Handle menu toggle interaction
  menuToggleBtn.addEventListener("click", () => {
    const isCurrentlyCollapsed = headerPanel.classList.contains("collapsed");
    if (isCurrentlyCollapsed) {
      headerPanel.classList.remove("collapsed");
      menuToggleBtn.setAttribute("aria-label", "Minimize menu");
      try {
        localStorage.setItem("did_menu_collapsed", "false");
      } catch (e) {}
    } else {
      headerPanel.classList.add("collapsed");
      menuToggleBtn.setAttribute("aria-label", "Expand menu");
      try {
        localStorage.setItem("did_menu_collapsed", "true");
      } catch (e) {}
    }
  });

  // Helper to resolve decade colors for chronological mapping
  function getDecadeColor(dateStr) {
    if (!dateStr) return "#9CA3AF";
    const match = dateStr.match(/\b(19\d{2}|20\d{2})\b/);
    if (!match) return "#9CA3AF";
    const year = parseInt(match[1], 10);
    if (year >= 1940 && year < 1950) return "#FCD34D"; // 1940s
    if (year >= 1950 && year < 1960) return "#F59E0B"; // 1950s
    if (year >= 1960 && year < 1970) return "#D97706"; // 1960s
    if (year >= 1970 && year < 1980) return "#EA580C"; // 1970s
    if (year >= 1980 && year < 1990) return "#E11D48"; // 1980s
    if (year >= 1990 && year < 2000) return "#14B8A6"; // 1990s
    if (year >= 2000 && year < 2010) return "#0D9488"; // 2000s
    if (year >= 2010 && year < 2020) return "#0F766E"; // 2010s
    if (year >= 2020 && year < 2030) return "#1E3A8A"; // 2020s
    return "#9CA3AF";
  }

  // Helper to extract the decade string from a broadcast date
  function getDecadeString(dateStr) {
    if (!dateStr) return "Unknown";
    const match = dateStr.match(/\b(19\d{2}|20\d{2})\b/);
    if (!match) return "Unknown";
    const year = parseInt(match[1], 10);
    const decadeStart = Math.floor(year / 10) * 10;
    return `${decadeStart}s`;
  }

  // Fetch the data.json database with cache-busting to force latest updates
  fetch("data.json?_t=" + Date.now())
    .then(res => res.json())
    .then(castaways => {

      let mappedCount = 0;
      let selectedMarker = null;
      const coordsSeen = {};
      const mappedMarkers = [];

      castaways.forEach(c => {
        let lat = c.bornInLat;
        let lng = c.bornInLng;

        // Plot dots only for guests who have resolved birthplace coordinates
        if (lat !== null && lng !== null) {
          mappedCount++;

          // Apply dynamic spiral dispersion jitter to resolve identical birth coordinates (e.g., London, New York)
          const coordKey = `${lat.toFixed(5)}_${lng.toFixed(5)}`;
          if (coordsSeen[coordKey]) {
            const count = coordsSeen[coordKey];
            const angle = count * 0.5; // Spiral expansion angle
            const radius = 0.0006 * Math.sqrt(count); // Spiral radius in degrees (~60m scale)
            lat += radius * Math.cos(angle);
            lng += radius * Math.sin(angle);
            coordsSeen[coordKey] = count + 1;
          } else {
            coordsSeen[coordKey] = 1;
          }

          const decadeColor = getDecadeColor(c.broadcastDate);

          // Plot beautiful clean "dots" using Canvas CircleMarkers
          const marker = L.circleMarker([lat, lng], {
            radius: 5.5,
            fillColor: decadeColor,
            color: "#FFFFFF",     // White border
            weight: 1.5,
            fillOpacity: 0.8,
            opacity: 1
          }).addTo(map);

          marker.decadeColor = decadeColor; // Save for dynamic highlights and transitions
          marker.decade = getDecadeString(c.broadcastDate); // Save decade string for filtering
          marker.castaway = c; // Reference castaway data directly on marker
          mappedMarkers.push(marker);

          // Construct rich tooltip details (shows on mouseover)
          const tooltipContent = `
            <strong>${c.name}</strong><br/>
            <span style="color: ${decadeColor}; font-size: 11px; font-weight: 600;">
              Born in: ${c.bornIn}
            </span><br/>
            <span style="color: #6B7280; font-size: 10px; font-style: italic;">
              Broadcasted: ${c.broadcastDate}
            </span>
          `;

          // Bind tooltip with micro-adjustments
          marker.bindTooltip(tooltipContent, {
            direction: "top",
            offset: [0, -6],
            className: "leaflet-tooltip-own",
            permanent: false,
            sticky: true
          });

          // Add smooth micro-interactions (expand & color shift on hover)
          marker.on("mouseover", function () {
            // Expand and highlight only if this marker is not the active selected one
            if (selectedMarker !== this) {
              this.setStyle({
                radius: 8.5,
                fillColor: "#D97706", // Gold highlights
                fillOpacity: 1
              });
            }
            this.bringToFront();
          });

          marker.on("mouseout", function () {
            // Restore styles only if this marker is not the active selected one
            if (selectedMarker !== this) {
              this.setStyle({
                radius: 5.5,
                fillColor: this.decadeColor,
                fillOpacity: 0.8
              });
            }
          });

          // Click handler to slide in the sidebar details panel
          marker.on("click", function () {
            // Cleanly trigger mouseout on all markers to close any open tooltips and reset styles
            mappedMarkers.forEach(m => {
              m.fire("mouseout");
            });

            // Smoothly center the map on the clicked coordinate
            map.panTo([lat, lng]);

            // Reset style of previously selected marker
            if (selectedMarker && selectedMarker !== this) {
              selectedMarker.setStyle({
                radius: 5.5,
                fillColor: selectedMarker.decadeColor,
                fillOpacity: 0.8
              });
            }

            // Set current marker as selected and apply permanent highlight
            selectedMarker = this;
            this.setStyle({
              radius: 9,
              fillColor: "#D97706",
              fillOpacity: 1
            });

            // Open the tooltip programmatically to display birthplace details on the map
            this.openTooltip();

            // Slide in the details panel
            detailsPanel.classList.remove("hidden");

            // Format dynamic hero image HTML from BBC if imagePid is resolved
            let imageHtml = "";
            if (c.imagePid) {
              const imageUrl = `https://ichef.bbci.co.uk/images/ic/640x360/${c.imagePid}.jpg`;
              imageHtml = `
                <div class="details-hero">
                  <img src="${imageUrl}" alt="${c.name}" class="hero-img" loading="lazy" />
                  <span class="hero-caption">Image from BBC DID site</span>
                </div>
              `;
            }

            // Format dynamic Wikipedia action button if wikipediaUrl is resolved
            let wikiHtml = "";
            if (c.wikipediaUrl) {
              wikiHtml = `
                <a href="${c.wikipediaUrl}" target="_blank" rel="noopener noreferrer" class="wiki-btn">
                  Read on Wikipedia
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                    <polyline points="15 3 21 3 21 9"></polyline>
                    <line x1="10" y1="14" x2="21" y2="3"></line>
                  </svg>
                </a>
              `;
            }

            // Format HTML Content for the sidebar panel
            detailsContent.innerHTML = `
              ${imageHtml}
              <div class="details-header">
                <h2>${c.name}</h2>
                <div class="details-meta">
                  <span>Born in: ${c.bornIn}</span>
                  <span>Broadcast: ${c.broadcastDate}</span>
                </div>
              </div>
              <div class="details-body">
                ${c.description}
                <div class="details-actions">
                  <a href="${c.episodeUrl}" target="_blank" rel="noopener noreferrer" class="listen-btn">
                    Listen on BBC Sounds
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12"></line>
                      <polyline points="12 5 19 12 12 19"></polyline>
                    </svg>
                  </a>
                  ${wikiHtml}
                </div>
              </div>
            `;
          });
        }
      });

      // Update mapped counter and last updated date (derived dynamically from the latest episode in the dataset)
      document.getElementById("mapped-count").textContent = mappedCount;
      if (castaways.length > 0) {
        document.getElementById("last-updated-date").textContent = castaways[0].broadcastDate;
      }

      // Legend Decade Filtering Interaction
      const legendGrid = document.getElementById("legend-grid");
      const legendItems = legendGrid.querySelectorAll(".legend-item");
      let activeDecadeFilter = null;

      legendItems.forEach(item => {
        item.addEventListener("click", () => {
          const clickedDecade = item.getAttribute("data-decade");

          if (activeDecadeFilter === clickedDecade) {
            // Clicking the active filter a second time clears it
            activeDecadeFilter = null;
            legendGrid.classList.remove("filtering");
            item.classList.remove("active");
          } else {
            // Deactivate existing active filter
            legendItems.forEach(i => i.classList.remove("active"));
            
            // Set new active filter
            activeDecadeFilter = clickedDecade;
            legendGrid.classList.add("filtering");
            item.classList.add("active");
          }

          // Filter map markers in a single optimized pass
          let currentCount = 0;
          mappedMarkers.forEach(m => {
            if (activeDecadeFilter === null || m.decade === activeDecadeFilter) {
              if (!map.hasLayer(m)) {
                m.addTo(map);
              }
              currentCount++;
            } else {
              if (map.hasLayer(m)) {
                map.removeLayer(m);
              }
            }
          });

          // Close the details panel if the active selected castaway is hidden by the filter
          if (selectedMarker && !map.hasLayer(selectedMarker)) {
            detailsPanel.classList.add("hidden");
            selectedMarker.setStyle({
              radius: 5.5,
              fillColor: selectedMarker.decadeColor,
              fillOpacity: 0.8
            });
            selectedMarker = null;
          }

          // Dynamically adjust stats counter
          const countElement = document.getElementById("mapped-count");
          if (activeDecadeFilter) {
            countElement.innerHTML = `${currentCount} <span style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase;">in ${activeDecadeFilter}</span>`;
          } else {
            countElement.textContent = mappedCount;
          }
        });
      });

      // Autoplay Random Tour Logic
      const tourToggle = document.getElementById("tour-toggle");
      let tourInterval = null;

      tourToggle.addEventListener("change", (e) => {
        if (e.target.checked) {
          startTour();
        } else {
          stopTour();
        }
      });

      function startTour() {
        if (mappedMarkers.length === 0) return;
        stopTour(); // Defensively clear any existing interval
        jumpToRandom();
        tourInterval = setInterval(jumpToRandom, 5000);
      }

      function stopTour() {
        if (tourInterval) {
          clearInterval(tourInterval);
          tourInterval = null;
        }
      }

      function jumpToRandom() {
        // Filter random tour candidates to only contain currently visible markers
        const visibleMarkers = mappedMarkers.filter(m => map.hasLayer(m));
        if (visibleMarkers.length === 0) return;
        const randomIndex = Math.floor(Math.random() * visibleMarkers.length);
        const targetMarker = visibleMarkers[randomIndex];
        targetMarker.fire("click");
      }
    })
    .catch(err => {
      console.error("Error loading castaway dataset:", err);
    });
});

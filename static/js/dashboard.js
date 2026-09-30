/* =========================================================
   EMP TRACKER - ADMIN DASHBOARD JS
========================================================= */

"use strict";

console.log("EMP Tracker dashboard.js loaded successfully");


/* =========================================================
   GLOBAL CHART REFERENCES
========================================================= */

let adminProductionChart = null;
let employeePerformanceChart = null;


/* =========================================================
   SECTION TITLES
========================================================= */

const sectionTitles = {

    overview: {
        title: "Overview",
        subtitle: "Team performance overview"
    },

    performance: {
        title: "Performance",
        subtitle: "Employee productivity analysis"
    },

    leaderboard: {
        title: "Leaderboard",
        subtitle: "Team performance ranking"
    },

    production: {
        title: "Production",
        subtitle: "Employee production records"
    },

    quality: {
        title: "Quality",
        subtitle: "Quality and error monitoring"
    },

    errors: {
        title: "Errors",
        subtitle: "Employee-wise error categories"
    },

    "ai-error-analysis": {
        title: "AI Error Analysis",
        subtitle: "AI-powered Internal and Client Error Analysis"
    },

    employees: {
        title: "Employees",
        subtitle: "Complete employee list"
    },

    reports: {
        title: "Reports",
        subtitle: "Employee performance reports"
    }

};


/* =========================================================
   SHOW SECTION
========================================================= */

function adminShowSection(sectionId, clickedButton = null) {

    const sections =
        document.querySelectorAll(
            ".dashboard-section"
        );

    sections.forEach(function (section) {

        section.classList.remove("active");

    });


    const selectedSection =
        document.getElementById(sectionId);

    if (selectedSection) {

        selectedSection.classList.add("active");

    }


    /* -----------------------------------------------------
       SIDEBAR ACTIVE BUTTON
    ----------------------------------------------------- */

    const navButtons =
        document.querySelectorAll(
            ".sidebar-nav .nav-item"
        );

    navButtons.forEach(function (button) {

        button.classList.remove("active");

    });


    if (clickedButton) {

        clickedButton.classList.add("active");

    }
    else {

        navButtons.forEach(function (button) {

            const onclickValue =
                button.getAttribute("onclick") || "";

            if (
                onclickValue.includes(
                    "'" + sectionId + "'"
                )
                ||
                onclickValue.includes(
                    '"' + sectionId + '"'
                )
            ) {

                button.classList.add("active");

            }

        });

    }


    /* -----------------------------------------------------
       PAGE TITLE
    ----------------------------------------------------- */

    const pageTitle =
        document.getElementById(
            "adminPageTitle"
        );

    const pageSubtitle =
        document.getElementById(
            "adminPageSubtitle"
        );


    if (
        sectionTitles[sectionId]
    ) {

        if (pageTitle) {

            pageTitle.textContent =
                sectionTitles[sectionId].title;

        }


        if (pageSubtitle) {

            pageSubtitle.textContent =
                sectionTitles[sectionId].subtitle;

        }

    }


    /* -----------------------------------------------------
       CLOSE MOBILE SIDEBAR
    ----------------------------------------------------- */

    const sidebar =
        document.getElementById(
            "adminSidebar"
        );

    if (sidebar) {

        sidebar.classList.remove(
            "open"
        );

    }


    /* -----------------------------------------------------
       CREATE PERFORMANCE CHART
       ONLY WHEN PERFORMANCE SECTION OPENS
    ----------------------------------------------------- */

    if (
        sectionId === "performance"
    ) {

        setTimeout(
            function () {

                createEmployeePerformanceChart();

            },
            100
        );

    }


    /* -----------------------------------------------------
       CREATE DAILY PRODUCTION CHART
    ----------------------------------------------------- */

    if (
        sectionId === "overview"
    ) {

        setTimeout(
            function () {

                createDailyProductionChart();

            },
            100
        );

    }


    /* -----------------------------------------------------
       SCROLL TOP
    ----------------------------------------------------- */

    window.scrollTo({

        top: 0,

        behavior: "smooth"

    });

}


/* =========================================================
   BACKWARD COMPATIBILITY
========================================================= */

function showSection(sectionId, clickedButton = null) {

    adminShowSection(
        sectionId,
        clickedButton
    );

}


/* =========================================================
   MOBILE SIDEBAR
========================================================= */

function toggleAdminSidebar() {

    const sidebar =
        document.getElementById(
            "adminSidebar"
        );

    if (!sidebar) {
        return;
    }

    sidebar.classList.toggle(
        "open"
    );

}


/* =========================================================
   CLOSE SIDEBAR WHEN CLICKING OUTSIDE
========================================================= */

document.addEventListener(
    "click",
    function (event) {

        const sidebar =
            document.getElementById(
                "adminSidebar"
            );

        const menuButton =
            document.querySelector(
                ".mobile-menu-btn"
            );


        if (!sidebar) {
            return;
        }


        if (
            window.innerWidth <= 768
            &&
            sidebar.classList.contains("open")
            &&
            !sidebar.contains(event.target)
            &&
            !(
                menuButton &&
                menuButton.contains(event.target)
            )
        ) {

            sidebar.classList.remove(
                "open"
            );

        }

    }
);


/* =========================================================
   SAFE NUMBER
========================================================= */

function safeNumber(value) {

    const number =
        Number(value);

    if (
        Number.isFinite(number)
    ) {

        return number;

    }

    return 0;

}


/* =========================================================
   FORMAT NUMBER
========================================================= */

function formatNumber(value) {

    const number =
        safeNumber(value);

    return number.toLocaleString(
        "en-IN"
    );

}


/* =========================================================
   FORMAT PERCENTAGE
========================================================= */

function formatPercentage(value) {

    const number =
        safeNumber(value);

    return number.toFixed(2) + "%";

}


/* =========================================================
   DAILY PRODUCTION DATA
========================================================= */

function getDailyProductionData() {

    const raw =
        window.ADMIN_DAILY_PRODUCTION;


    if (
        !Array.isArray(raw)
    ) {

        return [];

    }


    return raw.map(function (item) {

        return {

            date:
                item.date ??
                item.Date ??
                "",

            value:
                safeNumber(
                    item.value ??
                    item.production ??
                    item["Total Production"]
                )

        };

    }).filter(function (item) {

        return (
            item.date !== ""
        );

    });

}


/* =========================================================
   DAILY PRODUCTION CHART
========================================================= */

function createDailyProductionChart() {

    const canvas =
        document.getElementById(
            "adminProductionChart"
        );


    if (!canvas) {

        console.log(
            "Daily production canvas not found"
        );

        return;

    }


    const data =
        getDailyProductionData();


    if (
        adminProductionChart
    ) {

        adminProductionChart.destroy();

        adminProductionChart = null;

    }


    if (
        data.length === 0
    ) {

        console.log(
            "No daily production data available"
        );

        return;

    }


    const labels =
        data.map(function (item) {

            return item.date;

        });


    const values =
        data.map(function (item) {

            return item.value;

        });


    const context =
        canvas.getContext("2d");


    adminProductionChart =
        new Chart(
            context,
            {

                type: "line",

                data: {

                    labels: labels,

                    datasets: [

                        {

                            label:
                                "Daily Production",

                            data:
                                values,

                            borderWidth: 3,

                            pointRadius: 4,

                            pointHoverRadius: 6,

                            tension: 0.35,

                            fill: true

                        }

                    ]

                },


                options: {

                    responsive: true,

                    maintainAspectRatio: false,

                    interaction: {

                        intersect: false,

                        mode: "index"

                    },


                    plugins: {

                        legend: {

                            display: true,

                            position: "top"

                        },


                        tooltip: {

                            callbacks: {

                                label:
                                    function (context) {

                                        return (
                                            " Production: "
                                            +
                                            formatNumber(
                                                context.parsed.y
                                            )
                                        );

                                    }

                            }

                        }

                    },


                    scales: {

                        x: {

                            title: {

                                display: true,

                                text: "Date"

                            },

                            grid: {

                                display: false

                            }

                        },


                        y: {

                            beginAtZero: true,

                            title: {

                                display: true,

                                text: "Production"

                            },

                            ticks: {

                                callback:
                                    function (value) {

                                        return formatNumber(
                                            value
                                        );

                                    }

                            }

                        }

                    }

                }

            }
        );

}


/* =========================================================
   PERFORMANCE DATA
========================================================= */

function getPerformanceData() {

    const raw =
        window.ADMIN_PERFORMANCE;


    if (
        !Array.isArray(raw)
    ) {

        return [];

    }


    return raw
        .map(function (employee) {

            return {

                name:
                    employee["User Name"] ??
                    employee["USERNAME"] ??
                    "Employee",

                productivity:
                    safeNumber(
                        employee["Productivity %"] ??
                        employee["Productivity"]
                    ),

                quality:
                    safeNumber(
                        employee["Quality %"] ??
                        employee["Quality"]
                    ),

                production:
                    safeNumber(
                        employee["Total Production"]
                    ),

                errors:
                    safeNumber(
                        employee["Total Errors"]
                    )

            };

        })
        .filter(function (employee) {

            return (
                employee.name &&
                employee.name.trim() !== ""
            );

        });

}


/* =========================================================
   EMPLOYEE PERFORMANCE CHART
   SHOW PRODUCTION GRAPH ONLY
========================================================= */
/* =========================================================
   EMPLOYEE PERFORMANCE CHART
   EMPLOYEE NAME ON X-AXIS
   PRODUCTION ON Y-AXIS
========================================================= */

function createEmployeePerformanceChart() {

    const canvas =
        document.getElementById("productivityChart");

    if (!canvas) {
        console.log("Performance chart canvas not found");
        return;
    }

    const data =
        getPerformanceData();

    if (employeePerformanceChart) {
        employeePerformanceChart.destroy();
        employeePerformanceChart = null;
    }

    if (data.length === 0) {
        console.log("No employee performance data available");
        return;
    }


    /* -----------------------------------------------------
       EMPLOYEE NAMES
    ----------------------------------------------------- */

    const labels =
        data.map(function (employee) {

            const fullName = employee.name.trim();

            // Take only the first name
            return fullName.split(/\s+/)[0];

        });


    /* -----------------------------------------------------
       PRODUCTION
    ----------------------------------------------------- */

    const production =
        data.map(function (employee) {
            return employee.production;
        });


    /* -----------------------------------------------------
       BIG CHART HEIGHT
    ----------------------------------------------------- */

    const chartHeight = Math.max(
        650,
        data.length * 70
    );

    canvas.style.height =
        chartHeight + "px";

    canvas.style.width =
        "100%";


    /* -----------------------------------------------------
       CANVAS CONTEXT
    ----------------------------------------------------- */

    const context =
        canvas.getContext("2d");


    /* -----------------------------------------------------
       CREATE CHART
    ----------------------------------------------------- */

    employeePerformanceChart =
        new Chart(
            context,
            {

                type: "bar",

                data: {

                    /*
                       EMPLOYEE NAMES
                       ARE NOW ON X-AXIS
                    */

                    labels: labels,

                    datasets: [

                        {

                            label:
                                "Production",

                            data:
                                production,

                            backgroundColor:
                                "#4CAF50",

                            borderColor:
                                "#4CAF50",

                            borderWidth:
                                1,

                            borderRadius:
                                7,


                            /*
                               SPACE BETWEEN BARS
                            */

                            barPercentage:
                                0.55,

                            categoryPercentage:
                                0.70

                        }

                    ]

                },


                options: {

                    /*
                       IMPORTANT:
                       Remove indexAxis: "y"
                       so names appear on X-axis.
                    */

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,


                    /* -------------------------------------
                       PLUGINS
                    ------------------------------------- */

                    plugins: {

                        legend: {

                            display:
                                true,

                            position:
                                "top",

                            labels: {

                                font: {

                                    weight:
                                        "bold",

                                    size:
                                        15

                                },

                                padding:
                                    25

                            }

                        },


                        tooltip: {

                            titleFont: {

                                weight:
                                    "bold",

                                size:
                                    14

                            },

                            bodyFont: {

                                weight:
                                    "bold",

                                size:
                                    13

                            },

                            callbacks: {

                                label:
                                    function (context) {

                                        return (
                                            " Production: "
                                            +
                                            formatNumber(
                                                context.raw
                                            )
                                        );

                                    }

                            }

                        }

                    },


                    /* -------------------------------------
                       SCALES
                    ------------------------------------- */

                    scales: {


                        /* ================================
                           X AXIS
                           EMPLOYEE NAMES
                        ================================= */

                        x: {

                            title: {

                                display:
                                    true,

                                text:
                                    "Employee Name",

                                font: {

                                    weight:
                                        "bold",

                                    size:
                                        16

                                }

                            },


                            ticks: {

                                /*
                                   SHOW ALL NAMES
                                */

                                autoSkip:
                                    false,

                                padding:
                                    15,

                                maxRotation:
                                    45,

                                minRotation:
                                    0,

                                font: {

                                    weight:
                                        "bold",

                                    size:
                                        14

                                }

                            },


                            grid: {

                                display:
                                    false

                            }

                        },


                        /* ================================
                           Y AXIS
                           PRODUCTION
                        ================================= */

                        y: {

                            beginAtZero:
                                true,


                            title: {

                                display:
                                    true,

                                text:
                                    "Production",

                                font: {

                                    weight:
                                        "bold",

                                    size:
                                        16

                                }

                            },


                            ticks: {

                                font: {

                                    weight:
                                        "bold",

                                    size:
                                        13

                                },

                                callback:
                                    function (value) {

                                        return formatNumber(
                                            value
                                        );

                                    }

                            }

                        }

                    }

                }

            }
        );

}


/* =========================================================
   PREPARE LEADERBOARD
========================================================= */

function prepareLeaderboardData() {

    const data =
        getLeaderboardData();


    data.sort(function (a, b) {

        return (
            b.productivity -
            a.productivity
        );

    });


    data.forEach(
        function (employee, index) {

            employee.rank =
                index + 1;

        }
    );


    return data;

}


/* =========================================================
   UPDATE LEADERBOARD RANKS
========================================================= */

function updateLeaderboardRanks() {

    const table =
        document.getElementById(
            "adminLeaderboardTable"
        );


    if (!table) {
        return;
    }


    const rows =
        table.querySelectorAll(
            "tbody tr"
        );


    let actualRank = 1;


    rows.forEach(function (row) {

        if (
            row.style.display === "none"
        ) {

            return;

        }


        const rankCell =
            row.querySelector(
                "td:first-child"
            );


        if (!rankCell) {
            return;
        }


        if (actualRank === 1) {

            rankCell.innerHTML =
                '<span class="rank-badge">🥇</span>';

        }

        else if (actualRank === 2) {

            rankCell.innerHTML =
                '<span class="rank-badge">🥈</span>';

        }

        else if (actualRank === 3) {

            rankCell.innerHTML =
                '<span class="rank-badge">🥉</span>';

        }

        else {

            rankCell.innerHTML =
                '<span class="rank-badge">#'
                +
                actualRank
                +
                '</span>';

        }


        actualRank++;

    });

}


/* =========================================================
   GENERIC TABLE SEARCH
========================================================= */

function setupTableSearch(
    inputId,
    tableId
) {

    const input =
        document.getElementById(
            inputId
        );

    const table =
        document.getElementById(
            tableId
        );


    if (
        !input ||
        !table
    ) {

        return;

    }


    input.addEventListener(
        "input",
        function () {

            const searchValue =
                this.value
                    .toLowerCase()
                    .trim();


            const rows =
                table.querySelectorAll(
                    "tbody tr"
                );


            rows.forEach(
                function (row) {

                    const rowText =
                        row.textContent
                            .toLowerCase();


                    if (
                        searchValue === ""
                        ||
                        rowText.includes(
                            searchValue
                        )
                    ) {

                        row.style.display =
                            "";

                    }

                    else {

                        row.style.display =
                            "none";

                    }

                }
            );


            if (
                tableId ===
                "adminLeaderboardTable"
            ) {

                updateLeaderboardRanks();

            }

        }
    );

}


/* =========================================================
   EMPLOYEE CARD SEARCH SUPPORT
========================================================= */

function filterEmployeeCards(
    searchValue
) {

    const cards =
        document.querySelectorAll(
            ".employee-card"
        );


    const value =
        String(
            searchValue || ""
        )
        .toLowerCase()
        .trim();


    cards.forEach(function (card) {

        const text =
            card.textContent
                .toLowerCase();


        card.style.display =
            (
                !value ||
                text.includes(value)
            )
            ? ""
            : "none";

    });

}


/* =========================================================
   SEARCH ALL TABLES
========================================================= */

function setupAllSearches() {

    setupTableSearch(
        "performanceSearch",
        "adminPerformanceTable"
    );


    setupTableSearch(
        "leaderboardSearch",
        "adminLeaderboardTable"
    );


    setupTableSearch(
        "productionSearch",
        "adminProductionTable"
    );


    setupTableSearch(
        "qualitySearch",
        "adminQualityTable"
    );


    setupTableSearch(
        "errorSearch",
        "adminErrorsTable"
    );

}


/* =========================================================
   TABLE ROW HIGHLIGHT
========================================================= */

function setupRowInteractions() {

    const tables =
        document.querySelectorAll(
            ".data-table, .leaderboard-table"
        );


    tables.forEach(function (table) {

        const rows =
            table.querySelectorAll(
                "tbody tr"
            );


        rows.forEach(function (row) {

            row.addEventListener(
                "click",
                function () {

                    rows.forEach(
                        function (otherRow) {

                            otherRow.classList.remove(
                                "selected-row"
                            );

                        }
                    );


                    row.classList.add(
                        "selected-row"
                    );

                }
            );

        });

    });

}


/* =========================================================
   RESIZE CHARTS
========================================================= */

window.addEventListener(
    "resize",
    function () {

        if (
            adminProductionChart
        ) {

            adminProductionChart.resize();

        }


        if (
            employeePerformanceChart
        ) {

            employeePerformanceChart.resize();

        }

    }
);


/* =========================================================
   INITIALIZATION
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        console.log(
            "Initializing EMP Tracker dashboard..."
        );


        setupAllSearches();


        setupRowInteractions();


        /* -------------------------------------------------
           INITIAL OVERVIEW CHART
        ------------------------------------------------- */

        createDailyProductionChart();


        /* -------------------------------------------------
           INITIAL ACTIVE NAV
        ------------------------------------------------- */

        const activeButton =
            document.querySelector(
                ".sidebar-nav .nav-item.active"
            );


        if (
            activeButton
        ) {

            activeButton.classList.add(
                "active"
            );

        }


        console.log(
            "EMP Tracker dashboard initialized"
        );

    }
);


/* =========================================================
   AI ERROR ANALYZER NAVIGATION
   AI-ONLY CHANGE
========================================================= */

function openAIErrorAnalyzer(clickedButton) {

    adminShowSection(
        'ai-error-analysis',
        clickedButton
    );

}
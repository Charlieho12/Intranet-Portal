const currentDate = document.getElementById('dateFiled');
const startDateInput = document.getElementById('start-date');
const endDateInput = document.getElementById('end-date');
var breakfastModal = document.getElementById('breakfastModal');

var todayDate = new Date();   
currentDate.value = formatDate(todayDate);

var currentConversionRate = 1; // Ensure currentConversionRate is defined

function setCurrentDateTime() {
    var now = new Date();
    var year = now.getFullYear();
    var month = (now.getMonth() + 1).toString().padStart(2, "0");
    var day = now.getDate().toString().padStart(2, "0");
    var hours = now.getHours().toString().padStart(2, "0");
    var minutes = now.getMinutes().toString().padStart(2, "0");

    var formattedDateTime = `${year}-${month}-${day}T${hours}:${minutes}`;

    const dateFiledInput = document.getElementById('dateFiled');
    if (dateFiledInput) {
        dateFiledInput.value = formattedDateTime;
    }
}

// Set current date & time on page load
document.addEventListener("DOMContentLoaded", setCurrentDateTime);


function showBreakfastModal(){
    const modal = document.getElementById("myModal");
    modal.classList.remove('hide');
    breakfastModal.classList.remove('hide');
    modal.style.width = "100%";
}



function calculateDateRange(startDate, endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
        return 0; // Return 0 days if dates are invalid
    }

    const difference = end - start;
    const range = Math.ceil(difference / (1000 * 60 * 60 * 24)) + 1;
    return range;
}

function handleDateChange() {
    const startDate = new Date(startDateInput.value);
    const endDate = new Date(endDateInput.value);
    const current = new Date(currentDate.value);
    const travelType = document.getElementById('travel-type').value;
    var range = calculateDateRange(startDate, endDate);
    
    // For past dates
    if (startDate < current) {
        if (travelType === '4') {
            // For Official Business, show a warning but allow it
            if (!confirm("You're selecting a start date in the past. Do you want to continue?")) {
                startDateInput.value = currentDate.value;
                return;
            }
        } else {
            // For other travel types, don't allow past dates
            startDateInput.value = currentDate.value;
            alert("Start date cannot be in the past!");
            return;
        }
    }
    
    // Other validations remain the same
    if (startDateInput.value === "") {
        endDateInput.value = "";
        alert("Select start date first before end date!");
    } else if (range <= 0) {
        alert("End date cannot be less than start date!");
        endDateInput.value = "";
        range = 0;
    } else if (startDateInput.value !== "" && endDateInput.value !== "") {
        showContainer();
    }
}
startDateInput.addEventListener('change',  handleDateChange);
endDateInput.addEventListener('change', function(){
    handleDateChange();
    displayDates();  
});

document.addEventListener("DOMContentLoaded", function() {
    const travelId = document.getElementById("travel-form").dataset.travelId;

    function updateApprovalTable() {
        fetch(`/api/travel/${travelId}/status`)
            .then(response => response.json())
        .then(data => {
                const tableBody = document.getElementById("approval-table-body");
                tableBody.innerHTML = "";
                data.approvers.forEach(approver => {
                    const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${approver.name}</td>
                        <td>${approver.position}</td>
                        <td>${approver.status}</td>
                        <td>${approver.dateApproved ? new Date(approver.dateApproved).toLocaleString() : "Pending"}</td>
                `;
                tableBody.appendChild(row);
            });
            })
            .catch(error => console.error("Error fetching approval status:", error));
    }

    function sendApprovalRequest(url, action, remarks, approverName) {
        fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approver: approverName, remarks })
        })
        .then(response => response.json())
        .then(data => {
            alert(`Travel request ${action}: ${data.message}`);
            updateApprovalTable();
        })
        .catch(error => {
            console.error("Error:", error);
            alert("An error occurred while processing the request.");
        });
    }

    document.getElementById("approve-btn").addEventListener("click", function() {
       sendApprovalRequest(`/api/travel/${travelId}/approve`, "approved", "", "Yodo Kawase");
    });

    document.getElementById("reject-btn").addEventListener("click", function() {
        const remarks = document.getElementById("remarks").value.trim();
        if (!remarks) {
            alert("Please provide remarks for rejection.");
            return;
        }
        sendApprovalRequest(`/api/travel/${travelId}/reject`, "rejected", remarks, "Yodo Kawase");
    });

    setInterval(updateApprovalTable, 5000); // Refresh approval status every 5 seconds
    updateApprovalTable(); // Initial load

    const transportRequired = document.getElementById('transport-required');
    if (transportRequired) {
        transportRequired.addEventListener('change', function() {
            const transportOptions = document.getElementById('transport-options');
            if (transportOptions) {
                if (this.checked) {
                    transportOptions.style.display = 'block';
                } else {
                    transportOptions.style.display = 'none';
                    // Uncheck all transport options when transportation is unchecked
                    const checkboxes = transportOptions.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = false;
                    });
                }
            }
        });
    }
});

let lastToaNumber = 0; // This should ideally come from the server

function generateToaNumber() {
    lastToaNumber += 1; // Increment the last TOA number
    const formattedNumber = String(lastToaNumber).padStart(5, '0'); // Pad with leading zeros
    return `TOA-${formattedNumber}`;
}

document.querySelector('form').addEventListener('submit', function (e) {
    e.preventDefault(); // Prevent default form submission

    // Generate the TOA number
    const toaNumber = generateToaNumber();

    // Update the approval link
    const approvalLink = `/approval/${toaNumber}`;
    console.log('Approval Link:', approvalLink); // Debugging purpose
});

function displayDates() {
    const startDate = new Date(startDateInput.value);
    const endDate = new Date(endDateInput.value);
    const dateholder = document.getElementById("itenirary-holder");
    dateholder.innerHTML = "";

    // Reset meal quantities
    let breakfastQty = 0;
    let lunchQty = 0;
    let dinnerQty = 0;

    // Generate itinerary rows
    for (let currentDate = new Date(startDate); currentDate <= endDate; currentDate.setDate(currentDate.getDate() + 1)) {
    const row = document.createElement("tr");

    // Day
    const dayCell = document.createElement("td");
    dayCell.textContent = currentDate.toLocaleDateString('en-US', { weekday: 'long' });

    // Date (DD/MM/YYYY format)
    const dateCell = document.createElement("td");
    const day = currentDate.getDate().toString().padStart(2, '0');
    const month = (currentDate.getMonth() + 1).toString().padStart(2, '0');
    dateCell.textContent = `${day}/${month}/${currentDate.getFullYear()}`;

    // Get the selected travel type
    const travelType = document.getElementById("travel-type").value;
    const isOfficialBusiness = travelType === "4";
    const isLocked = travelType === "2" || travelType === "3";

   if (isOfficialBusiness) {
        // Meal Allowance (single checkbox)
        const mealAllowanceCell = document.createElement("td");
        const mealAllowanceCheckbox = document.createElement("input");
        mealAllowanceCheckbox.type = "checkbox";
        mealAllowanceCheckbox.className = "meal-checkbox meal-allowance";
        mealAllowanceCheckbox.checked = true;         // Always checked
        mealAllowanceCheckbox.disabled = true;        // Not editable
        mealAllowanceCell.appendChild(mealAllowanceCheckbox);

        // Activity
        const activityCell = document.createElement("td");
        const activityTextarea = document.createElement("textarea");
        activityTextarea.className = "activity-input";
        activityTextarea.placeholder = "Activity here...";
        activityTextarea.required = true;
        activityCell.appendChild(activityTextarea);

        row.append(dayCell, dateCell, mealAllowanceCell, activityCell);
    } else {
        // Breakfast
        const breakfastCell = document.createElement("td");
        const breakfastCheckbox = document.createElement("input");
        breakfastCheckbox.type = "checkbox";
        breakfastCheckbox.className = "meal-checkbox breakfast";
        breakfastCheckbox.checked = true;
        breakfastCheckbox.disabled = isLocked;
        breakfastCell.appendChild(breakfastCheckbox);

        // Lunch
        const lunchCell = document.createElement("td");
        const lunchCheckbox = document.createElement("input");
        lunchCheckbox.type = "checkbox";
        lunchCheckbox.className = "meal-checkbox lunch";
        lunchCheckbox.checked = true;
        lunchCheckbox.disabled = isLocked;
        lunchCell.appendChild(lunchCheckbox);

        // Dinner
        const dinnerCell = document.createElement("td");
        const dinnerCheckbox = document.createElement("input");
        dinnerCheckbox.type = "checkbox";
        dinnerCheckbox.className = "meal-checkbox dinner";
        dinnerCheckbox.checked = true;
        dinnerCheckbox.disabled = isLocked;
        dinnerCell.appendChild(dinnerCheckbox);

        // Activity
        const activityCell = document.createElement("td");
        const activityTextarea = document.createElement("textarea");
        activityTextarea.className = "activity-input";
        activityTextarea.placeholder = "Activity here...";
        activityTextarea.required = true;
        activityCell.appendChild(activityTextarea);

        row.append(dayCell, dateCell, breakfastCell, lunchCell, dinnerCell, activityCell);
    }

    dateholder.appendChild(row);
}
    
    // Show the container
    showContainer();
}

// Helper function to format date as DD/MM/YYYY
function formatDate(date) {
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

function showContainer(){
    var container = document.getElementById('itenirary-container');
    container.classList.remove('hide');
}

document.getElementById('proceed-cash-advance-btn').addEventListener('click', function() {
    document.getElementById('requiresCashAdvance').value = 'true';
    document.querySelector('form').requestSubmit();
});


document.getElementById('submit-btn').addEventListener('click', function() {
    document.getElementById('requiresCashAdvance').value = 'false';
});

document.querySelector('form').addEventListener('submit', async (e) => {
            e.preventDefault();

        const travelType = document.getElementById('travel-type').value;
        const isInternational = travelType === "2";

        // Get destinations based on active container
        let destinationsArray = [];
        const activeContainer = document.querySelector('.destination-container:not([style*="display: none"])');

        if (activeContainer) {
            destinationsArray = Array.from(activeContainer.querySelectorAll('.dest')).map(dest => dest.value.trim());
        }
        
        const dateFiledInput = document.getElementById('dateFiled');
        let dateFiledValue = dateFiledInput.value;

        // If time is missing, add the current time
        if (dateFiledValue.length === 10) {  // Check if format is only 'YYYY-MM-DD'
            let now = new Date();
            let hours = now.getHours().toString().padStart(2, "0");
            let minutes = now.getMinutes().toString().padStart(2, "0");
            dateFiledValue += `T${hours}:${minutes}`;
        }

        const itinerary = [];
        const rows = document.querySelectorAll('#itenirary-holder tr');
        rows.forEach(row => {
            const cells = row.cells;
            itinerary.push({
                day: cells[0].textContent,
                date: cells[1].textContent,
                meals: {
                    breakfast: cells[2].querySelector('input').checked,
                    lunch: cells[3].querySelector('input').checked,
                    dinner: cells[4].querySelector('input').checked
                },
                activity: cells[5].querySelector('textarea').value
            });
        });

        // Get the travel mode selection
        let travelMode = '';
        const travelModeRadios = document.querySelectorAll('input[name="travel-mode"]');
        for (const radio of travelModeRadios) {
            if (radio.checked) {
                travelMode = radio.value;
                break;
            }
        }

        const paymentMethod = document.getElementById('payment-method').value;

        // Get hotel and transportation requirements
        const requiresHotel = document.getElementById('hotel-required') ? 
                            document.getElementById('hotel-required').checked : false;
        
        const requiresTransportation = document.getElementById('transport-required') ? 
                                    document.getElementById('transport-required').checked : false;
        
        // Get transportation types if transportation is required
        const transportationTypes = [];
        if (requiresTransportation) {
            document.querySelectorAll('input[name="transport-type[]"]:checked').forEach(checkbox => {
                transportationTypes.push(checkbox.value);
            });
        }


        const formData = {
            toaNumber: document.getElementById('toaNumber').value,
            dateFiled: dateFiledValue,
            travelType: document.getElementById('travel-type').value,
            isInternational: isInternational,
            employeeId: document.getElementById('employeeId').value,
            employee: document.getElementById('employeeName').value,
            department: document.getElementById('department').value,
            position: document.getElementById('position').value,
            startDate: document.getElementById('start-date').value,
            endDate: document.getElementById('end-date').value,
            origin: document.getElementById('origin').value,
            destinations: Array.from(document.querySelectorAll('.dest')).map(dest => dest.value),
            purpose: document.querySelector('.purpose textarea').value,
            approvalStatus: 'Pending',
            remarks: document.getElementById('modal-textarea').value,
            itinerary: itinerary,
            travelMode: travelMode,
            paymentMethod: paymentMethod,
            requiresHotel: requiresHotel,
            requiresTransportation: requiresTransportation,
            transportationTypes: transportationTypes,
            carRentalRequested : $('#car-rental-request').is(':checked'),
            requiresVerification: requiresHotel,
            requiresCashAdvance: document.getElementById('requiresCashAdvance').value === 'true'
        };
        
        if($('#transport-required').is(':checked') && $('#travel-mode-land').is(':checked')) {
            $('input[name="transport-type[]"]:checked').each(function() {
                formData.transportationTypes.push($(this).val());
            });
        }

        
        
        //http://172.20.238.158:5000/api/travel
        try {
            console.log('Form Data:', formData);
            $.ajax({
                url: '/api/travel',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(formData),
                success: async function(response) {

                    if ($('#car-rental-request').is(':checked')) {
                        await $.ajax({
                            url: '/api/request-car-rental',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({
                                employeeId: $('#employeeId').val(),
                                employeeName: $('#employeeName').val(),
                                toaNumber: response.toaNumber
                            })
                        });
                    }

                    // Redirect to cash advance page
                    window.location.href = response.redirect;
                },
                error: function(error) {
                    alert('Failed to submit TOA.');
                }
            });
        } catch (err) {
            alert('Error submitting travel request: ' + err.message);
        }
    });


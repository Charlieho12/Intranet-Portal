$(document).ready(function() {
    if (!obNumber) {
        console.error("Official Business Number (obNumber) is not defined.");
        alert("Error: OB Number is missing. Cannot load details.");
        return;
    }
    if (!currentUserId) {
        console.error("Current User ID (currentUserId) is not defined.");
    }

    console.log("Official Business Approval Page for OB #:", obNumber);
    console.log("Current User ID:", currentUserId);

    loadOBDetails();
    pollApprovalStatus(); // Start polling

    $('#approve-btn').on('click', approveOB);
    $('#reject-btn').on('click', rejectOB);
    $('#proceed-btn').on('click', proceedToCashAdvance);
});

function printPage() {
    if (event) event.preventDefault();
    window.print();
    return false;
}

function proceedToCashAdvance() {
    if (obNumber) {
        window.location.href = `/cash-advance-form/${obNumber}?type=OB`;
    } else {
        alert("OB Number is missing.");
    }
}

function formatDisplayDateTime(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return 'Invalid Date';
        return date.toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true });
    } catch (e) {
        return 'Invalid Date';
    }
}

function formatDateForDisplay(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return 'Invalid Date';
        // Format to YYYY-MM-DD
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    } catch (e) {
        return 'Invalid Date';
    }
}


function loadOBDetails() {
    $.get(`/api/official-business/${obNumber}`, function(data) {
        console.log("Fetched OB Data:", data);

        $('#dateFiled').val(formatDisplayDateTime(data.dateFiled));
        $('#employeeId').val(data.employeeId);
        $('#employeeName').val(data.employeeName || data.employee); // Use employeeName or fallback to employee
        $('#department').val(data.department);
        $('#position').val(data.position);
        $('#startDate').val(formatDateForInput(data.startDate));
        $('#endDate').val(formatDateForInput(data.endDate));
        $('#origin').val(data.origin);
        $('#purpose').val(data.purpose);

        // Populate destinations
        const destinationsContainer = $('#destinations-list');
        destinationsContainer.empty();
        if (data.destinations && data.destinations.length > 0) {
            data.destinations.forEach(dest => {
                if (dest && dest.trim() !== '') {
                    destinationsContainer.append(`<div class="destination-box subhead-text">${dest}</div>`);
                }
            });
        } else {
            destinationsContainer.append(`<div class="destination-box subhead-text">No destination specified</div>`);
        }

        // Populate Services Required
        populateServicesRequired(data);
        
        // Populate approvers table and check button states
        updateApprovalTable(data.approvers || []);

        // Show "Proceed to Cash Advance" button if applicable (e.g., if OB is approved and requires cash advance)
        if (data.approvalStatus === 'Approved' && data.requiresCashAdvance) {
            $('#proceed-btn').show();
        } else {
            $('#proceed-btn').hide();
        }

    }).fail(function(jqXHR, textStatus, errorThrown) {
        console.error("Error fetching OB details:", textStatus, errorThrown, jqXHR.responseText);
        alert("Failed to load Official Business details. Please check the console.");
    });
}

function populateServicesRequired(data) {
    const container = $('#services-required-display');
    container.empty();
    let servicesHtml = '';

    if (data.requiresHotel) {
        servicesHtml += `<div class="checkbox-display"><span class="checkbox-icon">✓</span><span class="checkbox-label">Hotel Accommodation</span></div>`;
    } else {
         servicesHtml += `<div class="checkbox-display"><span class="checkbox-icon"></span><span class="checkbox-label">Hotel Accommodation</span></div>`;
    }

    if (data.requiresTransportation) {
        servicesHtml += `<div class="checkbox-display"><span class="checkbox-icon">✓</span><span class="checkbox-label">Transportation</span></div>`;
        if (data.transportationTypes && data.transportationTypes.length > 0) {
            servicesHtml += `<div class="nested-options">`;
            data.transportationTypes.forEach(type => {
                servicesHtml += `<div class="checkbox-display"><span class="checkbox-icon">-</span><span class="checkbox-label">${type}</span></div>`;
            });
            servicesHtml += `</div>`;
        }
    } else {
        servicesHtml += `<div class="checkbox-display"><span class="checkbox-icon"></span><span class="checkbox-label">Transportation</span></div>`;
    }
    
    if (!servicesHtml) {
        servicesHtml = '<p>No specific services listed.</p>';
    }
    container.html(servicesHtml);
}

function formatDateForInput(dateString) {
            if (!dateString) return '';
            
            try {
                const date = new Date(dateString);
                if (isNaN(date.getTime())) {
                    console.warn("Invalid date:", dateString);
                    return '';
                }
                
                // Convert to YYYY-MM-DD format
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                
                return `${year}-${month}-${day}`;
            } catch (e) {
                console.error("Date formatting error:", e);
                return '';
            }
        }

function updateApprovalTable(approvers) {
    var approvalTableBody = $('#approval-table-body');
    approvalTableBody.empty();

    if (!approvers || !Array.isArray(approvers) || approvers.length === 0) {
        console.warn("Approvers data is missing or invalid:", approvers);
        approvalTableBody.append(`<tr><td colspan="4" class="text-center">No approvers found or data is invalid.</td></tr>`);
        return;
    }

    const approverStatusCheck = checkCurrentApproverStatus(approvers);
    
    if (!approverStatusCheck.canApprove) {
        $('#approve-btn, #reject-btn').prop('disabled', true).addClass('btn-disabled');
        $('#remarks').prop('readonly', true).addClass('input-disabled');
        
        if (approverStatusCheck.message) {
            if (!$('.approval-status-message').length) {
                $('<div class="approval-status-message"></div>')
                    .text(approverStatusCheck.message)
                    .insertBefore('#approval-table-body'); // Or a more suitable location
            } else {
                $('.approval-status-message').text(approverStatusCheck.message);
            }
        }
    } else {
        $('#approve-btn, #reject-btn').prop('disabled', false).removeClass('btn-disabled');
        $('#remarks').prop('readonly', false).removeClass('input-disabled');
        $('.approval-status-message').remove();
    }

    approvers.forEach(approver => {
        var status = approver.status || 'Pending';
        var dateApproved = (approver.dateApproved && typeof approver.dateApproved === 'string')
            ? formatDate(approver.dateApproved)
            : 'Pending';
        const isCurrentUserApprover = approver.employeeId === currentUserId;
        const rowClass = isCurrentUserApprover ? 'current-user-row' : '';

        approvalTableBody.append(`
            <tr class="${rowClass}">
                <td>${approver.name}</td>
                <td>${approver.position || 'N/A'}</td>
                <td>${status}</td>
                <td>${dateApproved}</td>
            </tr>
        `);
    });
}

function formatDate(dateString) {
    if (!dateString) return 'Pending'; 

    let processedDateString = dateString;
    const isoPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?$/;
    if (isoPattern.test(dateString)) {
        processedDateString += 'Z'; 
    }

    var date = new Date(processedDateString);

    if (isNaN(date.getTime())) {
        
        console.warn(`Failed to parse date string: '${dateString}' (processed as '${processedDateString}')`);
        
        date = new Date(dateString); 
        if (isNaN(date.getTime())) {
            return 'Pending'; 
        }
    }

    try {
        return date.toLocaleString('en-US', { 
            timeZone: 'Asia/Manila',
            year: 'numeric',
            month: 'numeric', 
            day: 'numeric',   
            hour: 'numeric', 
            minute: '2-digit', 
            second: '2-digit', 
            hour12: true
        });
    } catch (e) {
        // Fallback for browsers that might not support the timezone or options fully
        console.warn("Error formatting date to Asia/Manila, falling back to client's local string:", e, dateString);
        return date.toLocaleString(); // Fallback to client's local settings
    }
}

function checkCurrentApproverStatus(approvers) {
    if (!currentUserId) {
        console.warn("Current user ID not available for status check.");
        return { canApprove: false, status: 'error', message: 'User information missing.' };
    }
    const currentApprover = approvers.find(approver => approver.employeeId === currentUserId);
    
    if (!currentApprover) {
        return { canApprove: false, status: 'not-approver', message: 'You are not listed as an approver for this request.'};
    }
    
    if (currentApprover.status === 'Approved') {
        return { canApprove: false, status: 'approved', message: 'You have already APPROVED this request.' };
    }
    
    if (currentApprover.status === 'Rejected') {
        return { canApprove: false, status: 'rejected', message: 'You have already REJECTED this request.' };
    }
    
    
    return { canApprove: true, status: 'pending', message: '' };
}

function sendBackRequest() {
    var remarks = $('#remarks').val().trim();
    if (!remarks) {
        alert('Remarks are required to send back the Official Business.');
        return;
    }
    if (!confirm('Are you sure you want to send back this Official Business for revision?')) {
        return;
    }
    $.ajax({
        url: `/api/official-business/${obNumber}/send-back`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ remarks: remarks }),
        success: function(response) {
            alert('Official Business has been sent back for revision.');
            window.location.href = '/home';
        },
        error: function(xhr) {
            alert('Error sending back Official Business: ' + (xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'Unknown error'));
        }
    });
}

async function approveOB(event) {
    if (event) event.preventDefault();
    if ($('#approve-btn').prop('disabled')) {
        alert('You cannot approve this request at this time or have already made a decision.');
        return false;
    }
    
    try {
        const response = await fetch(`/api/official-business/${obNumber}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ remarks: $('#remarks').val() }) // Send remarks even on approval if desired
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Failed to approve. Unknown server error.' }));
            throw new Error(errorData.error || 'Failed to approve Official Business request');
        }

        const data = await response.json();
        alert(data.message || 'Official Business request approved successfully.');
        loadOBDetails(); // Reload details to refresh everything
    } catch (error) {
        console.error('Error approving OB:', error);
        alert('An error occurred: ' + error.message);
    }
}

async function rejectOB(event) {
    if (event) event.preventDefault();
    if ($('#reject-btn').prop('disabled')) {
        alert('You cannot reject this request at this time or have already made a decision.');
        return false;
    }
    
    const remarks = $('#remarks').val().trim();
    if (!remarks) {
        alert("Remarks are required for rejection.");
        $('#remarks').focus();
        return;
    }
    
    try {
        const response = await fetch(`/api/official-business/${obNumber}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ remarks: remarks })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Failed to reject. Unknown server error.' }));
            throw new Error(errorData.error || 'Failed to reject Official Business request');
        }

        const data = await response.json();
        alert(data.message || 'Official Business request rejected successfully.');
        loadOBDetails(); // Reload details to refresh everything
    } catch (error) {
        console.error('Error rejecting OB:', error);
        alert('An error occurred: ' + error.message);
    }
}
        
function pollApprovalStatus() {
    setInterval(() => {
        // Only fetch status if the user hasn't already made a decision
        // This check can be more sophisticated, e.g., by checking a global flag
        if (!$('#approve-btn').prop('disabled')) {
            $.get(`/api/official-business/${obNumber}/status`, function(data) {
                if (data && data.approvers) {
                    updateApprovalTable(data.approvers);
                     // Update cash advance button visibility based on overall status
                    if (data.approvalStatus === 'Approved' && data.requiresCashAdvance) {
                        $('#proceed-btn').show();
                    } else {
                        $('#proceed-btn').hide();
                    }
                }
            }).fail(function(jqXHR, textStatus, errorThrown) {
                console.warn("Polling for approval status failed:", textStatus, errorThrown);
            });
        }
    }, 10000); // Poll every 10 seconds
}


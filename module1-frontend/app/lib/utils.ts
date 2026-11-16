export function formatDate(value: string): string {
    if (!value) return 'Not specified';

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    });
}

export function formatLocalToUTC(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }

    return date.toISOString().split('.')[0] + 'Z';
}

export function formatUTCToLocal(value: string): string {

    // 2. Parse it (JavaScript automatically reads the 'Z' and knows it is UTC)
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    // 3. Extract the local components and pad single digits with a leading zero
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');

    // 4. Combine into the desired format
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}